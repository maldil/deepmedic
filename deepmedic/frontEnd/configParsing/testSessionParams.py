# Copyright (c) 2016, Konstantinos Kamnitsas
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the BSD license. See the accompanying LICENSE file
# or read the terms at https://opensource.org/licenses/BSD-3-Clause.

from __future__ import absolute_import, print_function, division

import os
import pandas as pd

from deepmedic.frontEnd.configParsing.utils import abs_from_rel_path, parse_filelist, check_and_adjust_path_to_ckpt, \
    get_paths_from_df, parse_fpaths_of_channs_from_filelists


class TestSessionParameters(object) :
    #To be called from outside too.
    @staticmethod
    def get_session_name(sessionName) :
        return sessionName if sessionName is not None else "testSession"
    @staticmethod
    def errorIntNormZScoreTwoAppliesGiven():
        print("ERROR: In testing-config, for the variable (dictionary) norm_zscore_prms,"
              "\n\tif ['apply_to_all_channels': True] then it must ['apply_per_channel': None]"
              "\n\tOtherwise, requires ['apply_to_all_channels': False] if ['apply_per_channel': [..list..] ]"
              "\n\tExiting!")
        exit(1)


    def __init__(self,
                 log,
                 main_outp_folder,
                 out_folder_preds,
                 out_folder_fms,
                 n_classes,
                 cfg):
        # Importants for running session.
        # From Session:
        self.log = log
        self.main_outp_folder = main_outp_folder

        # From test config:
        self._session_name = self.get_session_name(cfg[cfg.SESSION_NAME])

        abs_path_cfg = cfg.get_abs_path_to_cfg()
        path_model = abs_from_rel_path(cfg[cfg.SAVED_MODEL], abs_path_cfg) if cfg[cfg.SAVED_MODEL] is not None else None
        self.model_ckpt_path = check_and_adjust_path_to_ckpt(self.log, path_model) if path_model is not None else None

        #Input:
        if cfg[cfg.DATAFRAME] is not None:  # get data from csv/dataframe
            self.csv_fname = abs_from_rel_path(cfg[cfg.DATAFRAME], abs_path_cfg)
            try:
                self.dataframe = pd.read_csv(self.csv_fname, skipinitialspace=True)
            except OSError:  # FileNotFoundError exception only in Py3, which is child of OSError.
                raise OSError("File given for dataframe does not exist: " + self.csv_fname)
            (self.channels_fpaths,
             self.gtLabelsFilepaths,
             self.roiMasksFilepaths,
             self.out_preds_fnames) = get_paths_from_df(self.log,
                                                        self.dataframe,
                                                        os.path.dirname(self.csv_fname),
                                                        req_gt=False)
        else:  # Get data input data from old variables.
            self.csv_fname = None
            self.dataframe = None
            self.channels_fpaths = parse_fpaths_of_channs_from_filelists(cfg[cfg.CHANNELS], abs_path_cfg)
            self.gtLabelsFilepaths = parse_filelist(abs_from_rel_path(cfg[cfg.GT_LABELS], abs_path_cfg), make_abs=True) if cfg[cfg.GT_LABELS] is not None else None
            self.roiMasksFilepaths = parse_filelist(abs_from_rel_path(cfg[cfg.ROI_MASKS], abs_path_cfg), make_abs=True) if cfg[cfg.ROI_MASKS] is not None else None
            self.out_preds_fnames = parse_filelist(abs_from_rel_path(cfg[cfg.NAMES_FOR_PRED_PER_CASE], abs_path_cfg)) if cfg[cfg.NAMES_FOR_PRED_PER_CASE] is not None else None

        #predictions
        self.saveSegmentation = cfg[cfg.SAVE_SEGM] if cfg[cfg.SAVE_SEGM] is not None else True
        self.saveProbMapsBoolPerClass = cfg[cfg.SAVE_PROBMAPS_PER_CLASS] if (cfg[cfg.SAVE_PROBMAPS_PER_CLASS] is not None and cfg[cfg.SAVE_PROBMAPS_PER_CLASS] != []) else [True]*n_classes
        self.filepathsToSavePredictionsForEachPatient = None  #Filled by call to self.makeFilepathsForPredictionsAndFeatures()
        self.suffixForSegmAndProbsDict = cfg[cfg.SUFFIX_SEGM_PROB] if cfg[cfg.SUFFIX_SEGM_PROB] is not None else {"segm": "Segm", "prob": "ProbMapClass"}
        self.batchsize = cfg[cfg.BATCHSIZE] if cfg[cfg.BATCHSIZE] is not None else 10
        #features:
        self.save_fms_flag = cfg[cfg.SAVE_INDIV_FMS] if cfg[cfg.SAVE_INDIV_FMS] is not None else False
        if self.save_fms_flag:
            indices_fms_per_pathtype_per_layer_to_save = [cfg[cfg.INDICES_OF_FMS_TO_SAVE_NORMAL]] +\
                                                         [cfg[cfg.INDICES_OF_FMS_TO_SAVE_SUBSAMPLED]] +\
                                                         [cfg[cfg.INDICES_OF_FMS_TO_SAVE_FC]]
            self.indices_fms_per_pathtype_per_layer_to_save = [item if item is not None else [] for item in indices_fms_per_pathtype_per_layer_to_save]
        else:
            self.indices_fms_per_pathtype_per_layer_to_save = None
        self.filepathsToSaveFeaturesForEachPatient = None #Filled by call to self.makeFilepathsForPredictionsAndFeatures()
        
        # ===================== PRE-PROCESSING ======================
        # === Data compatibility checks ===
        self.run_input_checks = cfg[cfg.RUN_INP_CHECKS] if cfg[cfg.RUN_INP_CHECKS] is not None else True
        # == Padding ==
        self.pad_input = cfg[cfg.PAD_INPUT] if cfg[cfg.PAD_INPUT] is not None else True
        # == Normalization ==
        norm_zscore_prms = {'apply_to_all_channels': False, # True/False
                            'apply_per_channel': None, # Must be None if above True. Else, List Bool per channel
                            'cutoff_percents': None, # None or [low, high], each from 0.0 to 100. Eg [5.,95.]
                            'cutoff_times_std': None, # None or [low, high], each positive Float. Eg [3.,3.]
                            'cutoff_below_mean': False}
        if cfg[cfg.NORM_ZSCORE_PRMS] is not None:
            for key in cfg[cfg.NORM_ZSCORE_PRMS]:
                norm_zscore_prms[key] = cfg[cfg.NORM_ZSCORE_PRMS][key]
        if norm_zscore_prms['apply_to_all_channels'] and norm_zscore_prms['apply_per_channel'] is not None:
            self.errorIntNormZScoreTwoAppliesGiven()
        if norm_zscore_prms['apply_per_channel'] is not None:
            assert len(norm_zscore_prms['apply_per_channel']) == len(cfg[cfg.CHANNELS]) # num channels
        # Aggregate params from all types of normalization:
        # norm_prms = None : No int normalization will be performed.
        # norm_prms['verbose_lvl']: 0: No logging, 1: Type of cutoffs and timing 2: Stats.
        self.norm_prms = {'verbose_lvl': cfg[cfg.NORM_VERB_LVL] if cfg[cfg.NORM_VERB_LVL] is not None else 0,
                          'zscore': norm_zscore_prms}
        
        # ============= OTHERS =============
        #Others useful internally or for reporting:
        self.numberOfCases = len(self.channels_fpaths)
        
        # ============= HIDDENS =============
        # no config allowed for these at the moment:
        self._makeFilepathsForPredictionsAndFeatures(out_folder_preds, out_folder_fms)
        
    def _makeFilepathsForPredictionsAndFeatures(self,
                                                absPathToout_folder_predsFromSession,
                                                absPathToout_folder_fmsFromSession
                                                ) :
        self.filepathsToSavePredictionsForEachPatient = []
        self.filepathsToSaveFeaturesForEachPatient = []
        if self.out_preds_fnames is not None : # standard behavior
            for case_i in range(self.numberOfCases) :
                filepathForCasePrediction = absPathToout_folder_predsFromSession + "/" + self.out_preds_fnames[case_i]
                self.filepathsToSavePredictionsForEachPatient.append( filepathForCasePrediction )
                filepathForCaseFeatures = absPathToout_folder_fmsFromSession + "/" + self.out_preds_fnames[case_i]
                self.filepathsToSaveFeaturesForEachPatient.append( filepathForCaseFeatures )
        else : # Names for predictions not given. Special handling...
            if self.numberOfCases > 1 : # Many cases, create corresponding namings for files.
                for case_i in range(self.numberOfCases) :
                    self.filepathsToSavePredictionsForEachPatient.append( absPathToout_folder_predsFromSession + "/pred_case" + str(case_i) + ".nii.gz" )
                    self.filepathsToSaveFeaturesForEachPatient.append( absPathToout_folder_predsFromSession + "/pred_case" + str(case_i) + ".nii.gz" )
            else : # Only one case. Just give the output prediction folder, the io.py will save output accordingly.
                self.filepathsToSavePredictionsForEachPatient.append( absPathToout_folder_predsFromSession )
                self.filepathsToSaveFeaturesForEachPatient.append( absPathToout_folder_predsFromSession )
    
    
    def get_path_to_load_model_from(self):
        return self.model_ckpt_path
    
    
    def print_params(self) :
        logPrint = self.log.print3
        logPrint("")
        logPrint("=============================================================")
        logPrint("=========== PARAMETERS OF THIS TESTING SESSION ==============")
        logPrint("=============================================================")
        logPrint("sessionName = " + str(self._session_name))
        logPrint("Model will be loaded from save = " + str(self.model_ckpt_path))
        logPrint("~~~~~~~~~~~~~~~~~~~~INPUT~~~~~~~~~~~~~~~~")
        logPrint("Dataframe (csv) filename = " + str(self.csv_fname))
        logPrint("Number of cases to perform inference on = " + str(self.numberOfCases))
        logPrint("Paths to the channels of each case = " + str(self.channels_fpaths))
        logPrint("Paths to provided GT labels per case = " + str(self.gtLabelsFilepaths))
        logPrint("Filepaths of the ROI Masks provided per case = " + str(self.roiMasksFilepaths))
        logPrint("Batch size = " + str(self.batchsize))
        
        logPrint("~~~~~~~~~~~~~~~~~~~OUTPUT~~~~~~~~~~~~~~~")
        logPrint("Path to the main output-folder = " + str(self.main_outp_folder))
        logPrint("Provided names to use to save results for each case = " + str(self.out_preds_fnames))
        
        logPrint("~~~~~~~Ouput-parameters for Predictions (segmentation and probability maps)~~~~")
        logPrint("Save the predicted segmentation = " + str(self.saveSegmentation))
        logPrint("Save the probability maps = " + str(self.saveProbMapsBoolPerClass))
        logPrint("Paths where to save predictions per case = " + str(self.filepathsToSavePredictionsForEachPatient))
        logPrint("Suffixes with which to save segmentations and probability maps = " + str(self.suffixForSegmAndProbsDict))
        if not (self.saveSegmentation or self.saveProbMapsBoolPerClass) :
            logPrint(">>> WARN: Segmentation and Probability Maps won't be saved. I guess you only wanted the feature maps?")
            
        logPrint("~~~~~~~Ouput-parameters for Feature Maps (FMs)~~~~~~")
        logPrint("Save FMs in individual images = " + str(self.save_fms_flag))
        logPrint("Indices of min/max FMs to save, per type of pathway (normal/subsampled/FC) and per layer = " + str(self.indices_fms_per_pathtype_per_layer_to_save))
        logPrint("Save Feature Maps at = " + str(self.filepathsToSaveFeaturesForEachPatient))
        
        logPrint("~~~~~~~~~~~~~~~~~~ PRE-PROCESSING ~~~~~~~~~~~~~~~~")
        logPrint("~~Data Compabitibility Checks~~")
        logPrint("Check whether input data has correct format (can slow down process) = " + str(self.run_input_checks))
        logPrint("~~Padding~~")
        logPrint("Pad Input Images = " + str(self.pad_input))
        if not self.pad_input :
            logPrint(">>> WARN: Inference near the borders of the image might be incomplete if not padded!" +\
                     "Although some speed is gained if no padding is used. It is task-specific. Your choice.")
        logPrint("~~Intensity Normalization~~")
        logPrint("Verbosity level = " + str(self.norm_prms['verbose_lvl']))
        logPrint("Z-Score parameters = " + str(self.norm_prms['zscore']))
        
        logPrint("========== Done with printing session's parameters ==========")
        logPrint("=============================================================\n")
        
    def get_args_for_testing(self) :
        
        validation0orTesting1 = 1
        
        args = [self.log,
                validation0orTesting1,
                {"segm": self.saveSegmentation, "prob": self.saveProbMapsBoolPerClass},
                
                self.channels_fpaths,
                self.gtLabelsFilepaths,
                self.roiMasksFilepaths,
                self.filepathsToSavePredictionsForEachPatient,
                self.suffixForSegmAndProbsDict,
                # Hyper parameters
                self.batchsize,
                # Data compatibility checks
                self.run_input_checks,
                # Pre-Processing
                self.pad_input,
                self.norm_prms,
                # For FM visualisation
                self.save_fms_flag,
                self.indices_fms_per_pathtype_per_layer_to_save,
                self.filepathsToSaveFeaturesForEachPatient
                ]
        
        return args





