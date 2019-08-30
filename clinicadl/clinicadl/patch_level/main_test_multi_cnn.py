import argparse
import os
import torchvision.transforms as transforms
from torch.utils.data import DataLoader

from .utils import MRIDataset_patch_by_index, test, hard_voting_to_tsvs, multi_cnn_soft_majority_voting
from tools.deep_learning.models import create_model, load_model
from tools.deep_learning.data import MinMaxNormalization, load_data, load_data_test

__author__ = "Junhao Wen"
__copyright__ = "Copyright 2018 The Aramis Lab Team"
__credits__ = ["Junhao Wen"]
__license__ = "See LICENSE.txt file"
__version__ = "0.1.0"
__maintainer__ = "Junhao Wen"
__email__ = "junhao.wen89@gmail.com"
__status__ = "Development"

parser = argparse.ArgumentParser(description="Argparser for Pytorch 3D patch-level multi-CNN for test the trained classifiers")

# Mandatory argument
parser.add_argument("caps_directory", type=str,
                    help="Path to the caps of image processing pipeline of DL")
parser.add_argument("diagnosis_tsv_path", type=str,
                    help="Path to the tsv containing all the test dataset")
parser.add_argument("output_dir", type=str,
                    help="Path to store the classification outputs and the tsv files containing the performances.")

# Data management
parser.add_argument('--selection', default="best_acc", choices=["best_acc", "best_loss"],
                    help="Evaluate the model performance based on which criterior")
parser.add_argument("--patch_size", default=50, type=int,
                    help="The patch size extracted from the MRI")
parser.add_argument("--patch_stride", default=50, type=int,
                    help="The stride for the patch extract window from the MRI")
parser.add_argument('--mode', default="test", choices=["test", "valid"],
                    help="Evaluate or test")

# train argument
# transfer learning
parser.add_argument("--network", default="Conv_4_FC_3",
                    help="Architecture of the network.")
parser.add_argument("--num_cnn", default=36, type=int,
                    help="How many CNNs we want to train in a patch-wise way."
                         "By default, we train each patch from all subjects for one CNN.")
parser.add_argument("--diagnoses_list", default=["sMCI", "pMCI"], type=str, nargs="+",
                    help="Labels based on binary classification.")
parser.add_argument('--split', default=0,
                    help="which fold to be tested.")

# Computational issues
parser.add_argument("--batch_size", default=32, type=int,
                    help="Batch size for training. (default=1)")
parser.add_argument("--num_workers", default=8, type=int,
                    help='the number of batch being loaded in parallel')
parser.add_argument("--gpu", default=False, action='store_true',
                    help="If use gpu or cpu. Empty implies cpu usage.")

# TODO: check the behavior of default for bool in argparser


def main(options):
    # Initialize the model
    model = create_model(options.network, options.gpu)
    transformations = transforms.Compose([MinMaxNormalization()])

    if options.mode == 'test':
        test_df = load_data_test(options.diagnosis_tsv_path, options.diagnoses)
    else:
        _, test_df = load_data(options.diagnosis_tsv_path, options.diagnoses, options.split,
                               n_splits=options.n_fold, baseline=True)

    # get the test accuracy for all the N classifiers
    for n in range(options.num_cnn):

        dataset = MRIDataset_patch_by_index(options.caps_directory, test_df, options.patch_size,
                                            options.patch_stride, n, transformations=transformations)

        data_loader = DataLoader(dataset,
                                 batch_size=options.batch_size,
                                 shuffle=False,
                                 num_workers=options.num_workers,
                                 drop_last=True,
                                 pin_memory=True)

        # load the best trained model during the training
        model_updated, best_epoch = load_model(model, os.path.join(options.output_dir, 'best_model_dir',
                                                                   "fold_" + str(options.n_fold), 'cnn-' + str(n),
                                                                   options.selection), options.gpu,
                                               filename='model_best.pth.tar')
        model_updated.eval()

        print("The best model was saved during training from fold %d at the %d -th epoch" % (int(options.n_fold), int(best_epoch)))

        subjects, y_ground, y_hat, proba, accuracy_batch_mean = test(model_updated, data_loader, options)
        print("Patch level balanced accuracy is %f" % accuracy_batch_mean)

        # write the test results into the tsv files
        hard_voting_to_tsvs(options.output_dir, options.split, subjects, y_ground, y_hat, proba, mode=options.mode,
                            patch_index=n)

    multi_cnn_soft_majority_voting(options.output_dir, options.split, options.num_cnn, options.mode)


if __name__ == "__main__":
    commandline = parser.parse_known_args()
    options = commandline[0]
    if commandline[1]:
        raise Exception("unknown arguments: %s" % (parser.parse_known_args()[1]))
    main(options)
