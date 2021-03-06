#!../bin/python
from __future__ import print_function

import subprocess
import os
import sys
import argparse

import bob.bio.base

import bob.core
logger = bob.core.log.setup("bob.bio.face")

# This is the default set of algorithms that can be run using this script.
all_databases = bob.bio.base.resource_keys('database')
# check, which databases can actually be assessed
available_databases = []

for database in all_databases:
  try:
    bob.bio.base.load_resource(database, 'database')
    available_databases.append(database)
  except:
    pass

# collect all algorithms that we provide baselines for
all_algorithms = ['eigenface', 'lda', 'gabor-graph', 'lgbphs', 'plda', 'bic']

try:
  # try if GMM-based algorithms are available
  bob.bio.base.load_resource('gmm', 'algorithm')
  bob.bio.base.load_resource('isv', 'algorithm')
  bob.bio.base.load_resource('ivector-cosine', 'algorithm')
  all_algorithms += ['gmm', 'isv', 'ivector']
except:
  print("Could not load the GMM-based algorithms. Did you specify bob.bio.gmm in your config file?")

try:
  # try if the CSU extension is enabled
  bob.bio.base.load_resource('lrpca', 'algorithm')
  bob.bio.base.load_resource('lda-ir', 'algorithm')
  all_algorithms += ['lrpca', 'lda-ir']
except:
  print("Could not load the algorithms from the CSU resources. Did you specify bob.bio.csu in your config file?")


def command_line_arguments(command_line_parameters):
  """Defines the command line parameters that are accepted."""

  # create parser
  parser = argparse.ArgumentParser(description='Execute baseline algorithms with default parameters', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  # add parameters
  # - the algorithm to execute
  parser.add_argument('-a', '--algorithms', choices = all_algorithms, default = ('eigenface',), nargs = '+', help = 'Select one (or more) algorithms that you want to execute.')
  parser.add_argument('--all', action = 'store_true', help = 'Select all algorithms.')
  # - the database to choose
  parser.add_argument('-d', '--database', choices = available_databases, default = 'atnt', help = 'The database on which the baseline algorithm is executed.')
  # - the database to choose
  parser.add_argument('-b', '--baseline-directory', default = 'baselines', help = 'The sub-directory, where the baseline results are stored.')
  # - the directories to write to
  parser.add_argument('-T', '--temp-directory', help = 'The directory to write temporary the data of the experiment into. If not specified, the default directory of the verify.py script is used (see ./bin/verify.py --help).')
  parser.add_argument('-R', '--result-directory', help = 'The directory to write the resulting score files of the experiment into. If not specified, the default directories of the verify.py script are used (see ./bin/verify.py --help).')

  # - use the Idiap grid -- option is only useful if you are at Idiap
  parser.add_argument('-g', '--grid', action = 'store_true', help = 'Execute the algorithm in the SGE grid.')
  # - run in parallel on the local machine
  parser.add_argument('-l', '--parallel', type=int, help = 'Run the algorithms in parallel on the local machine, using the given number of parallel threads')
  # - perform ZT-normalization
  parser.add_argument('-z', '--zt-norm', action = 'store_true', help = 'Compute the ZT norm for the files (might not be availabe for all databases).')

  # - just print?
  parser.add_argument('-q', '--dry-run', action = 'store_true', help = 'Just print the commands, but do not execute them.')

  # - evaluate the algorithm (after it has finished)
  parser.add_argument('-e', '--evaluate', nargs='+', choices = ('EER', 'HTER', 'ROC', 'DET', 'CMC', 'RR'), help = 'Evaluate the results of the algorithms (instead of running them) using the given evaluation techniques.')

  # - other parameters that are passed to the underlying script
  parser.add_argument('parameters', nargs = argparse.REMAINDER, help = 'Parameters directly passed to the ./bin/verify.py script.')

  bob.core.log.add_command_line_option(parser)
  args = parser.parse_args(command_line_parameters)
  if args.all:
    args.algorithms = all_algorithms

  bob.core.log.set_verbosity_level(logger, args.verbose)

  return args


# In these functions, some default experiments are prepared.
# An experiment consists of three configuration files:
# - The features to be extracted
# - The algorithm to be run
# - The grid configuration that it requires (only used when the --grid option is chosen)

CONFIGURATIONS = {
  'eigenface' : dict(
    preprocessor = ('face-crop-eyes', 'base'),
    extractor    = 'linearize',
    algorithm    = 'pca',
  ),

  'lda': dict(
    preprocessor = ('face-crop-eyes', 'base'),
    extractor    = 'eigenface',
    algorithm    = 'lda',
  ),

  'plda': dict(
    preprocessor = ('face-crop-eyes', 'base'),
    extractor    = 'linearize',
    algorithm    = 'pca+plda',
    grid         = 'demanding'
  ),

  'gabor-graph': dict(
    preprocessor = ('inorm-lbp-crop', 'inorm-lbp'),
    extractor    = 'grid-graph',
    algorithm    = 'gabor-jet',
  ),

  'lgbphs': dict(
    preprocessor = ('tan-triggs-crop', 'tan-triggs'),
    extractor    = 'lgbphs',
    algorithm    = 'histogram',
  ),

  'bic': dict(
    preprocessor = ('face-crop-eyes', 'base'),
    extractor    = 'grid-graph',
    algorithm    = 'bic-jets',
    grid         = 'demanding'
  ),

  'gmm': dict(
    preprocessor = ('tan-triggs-crop', 'tan-triggs'),
    extractor    = 'dct-blocks',
    algorithm    = 'gmm',
    grid         = 'demanding',
    script       = './bin/verify_gmm.py'
  ),

  'isv': dict(
    preprocessor = ('tan-triggs-crop', 'tan-triggs'),
    extractor    = 'dct-blocks',
    algorithm    = 'isv',
    grid         = 'demanding',
    script       = './bin/verify_isv.py'
  ),

  'ivector': dict(
    preprocessor = ('tan-triggs-crop', 'tan-triggs'),
    extractor    = 'dct-blocks',
    algorithm    = 'ivector-cosine',
    grid         = 'demanding',
    script       = './bin/verify_ivector.py'
  ),

  'lrpca': dict(
    preprocessor = ('lrpca', None),
    extractor    = 'lrpca',
    algorithm    = 'lrpca'
  ),

  'lda-ir': dict(
    preprocessor = ('lda-ir', None),
    extractor    = 'lda-ir',
    algorithm    = 'lda-ir'
  )
}

def main(command_line_parameters = None):

  # Collect command line arguments
  args = command_line_arguments(command_line_parameters)

  # Check the database configuration file
  has_eyes = args.database != 'atnt'
  has_zt_norm = args.database in ('banca', 'mobio', 'multipie', 'scface')
  has_eval = args.database in ('banca', 'mobio', 'multipie', 'scface', 'xm2vts')

  if not args.evaluate:

    # execution of the job is requested
    for algorithm in args.algorithms:
      logger.info("Executing algorithm '%s'", algorithm)

      # get the setup for the desired algorithm
      import copy
      setup = copy.deepcopy(CONFIGURATIONS[algorithm])
      if 'grid' not in setup: setup['grid'] = 'grid'
      if 'script' not in setup or (not args.grid and args.parallel is None): setup['script'] = './bin/verify.py'

      # select the preprocessor
      setup['preprocessor'] = setup['preprocessor'][0 if has_eyes else 1]
      if setup['preprocessor'] is None:
        logger.warn("Skipping algorithm '%s' since no preprocessor is found that matches the given databases' '%s' configuration", algorithm, args.database)


      # this is the default sub-directory that is used
      sub_directory = os.path.join(args.baseline_directory, algorithm)

      # create the command to the faceverify script
      command = [
          setup['script'],
          '--database', args.database,
          '--preprocessor', setup['preprocessor'],
          '--extractor', setup['extractor'],
          '--algorithm', setup['algorithm'],
          '--sub-directory', sub_directory
      ]

      # add grid argument, if available
      if args.grid:
        command += ['--grid', setup['grid'], '--stop-on-failure']

      if args.parallel is not None:
        command += ['--grid', 'bob.bio.base.grid.Grid("local", number_of_parallel_processes=%d)' % args.parallel, '--run-local-scheduler', '--stop-on-failure']

      # compute ZT-norm if the database provides this setup
      if has_zt_norm and args.zt_norm:
        command += ['--zt-norm']

      # compute results for both 'dev' and 'eval' group if the database provides these
      if has_eval:
        command += ['--groups', 'dev', 'eval']

      # set the directories, if desired
      if args.temp_directory is not None:
        command += ['--temp-directory', os.path.join(args.temp_directory)]
      if args.result_directory is not None:
        command += ['--result-directory', os.path.join(args.result_directory)]

      # set the verbosity level
      if args.verbose:
        command += ['-' + 'v'*args.verbose]

      # add the command line arguments that were specified on command line
      if args.parameters:
        command += args.parameters[1:]

      # print the command so that it can easily be re-issued
      logger.info("Executing command:\n%s", bob.bio.base.tools.command_line(command))

      # run the command
      if not args.dry_run:
        subprocess.call(command)

  else:
    # call the evaluate script with the desired parameters

    # get the base directory of the results
    is_idiap = os.path.isdir("/idiap")
    if args.result_directory is None:
      args.result_directory = "/idiap/user/%s/%s" % (os.environ["USER"], args.database) if is_idiap else "results"
    if not os.path.exists(args.result_directory):
      if not args.dry_run:
        raise IOError("The result directory '%s' cannot be found. Please specify the --result-directory as it was specified during execution of the algorithms." % args.result_directory)

    # get the result directory of the database
    result_dir = os.path.join(args.result_directory, args.baseline_directory)
    if not os.path.exists(result_dir):
      if not args.dry_run:
        raise IOError("The result directory '%s' for the desired experiment cannot be found. Did you already run the experiments?" % result_dir)

    # iterate over the algorithms and collect the result files
    result_dev = []
    result_eval = []
    result_zt_dev = []
    result_zt_eval = []
    legends = []

    # evaluate the results
    for algorithm in args.algorithms:
      if not os.path.exists(os.path.join(result_dir, algorithm)):
        logger.warn("Skipping algorithm '%s' since the results cannot be found.", algorithm)
        continue
      protocols = [d for d in os.listdir(os.path.join(result_dir, algorithm)) if os.path.isdir(os.path.join(result_dir, algorithm, d))]
      if not len(protocols):
        logger.warn("Skipping algorithm '%s' since the results cannot be found.", algorithm)
        continue
      if len(protocols) > 1:
        # load the default protocol of the database
        protocol = bob.bio.base.load_resource(args.database, "database").protocol
        if protocol not in protocols:
          protocol = protocols[0]
          logger.warn("There are several protocols found in directory '%s'. Here, we use protocol '%s'.", os.path.join(result_dir, algorithm), protocols[0])
      else:
        protocol = protocols[0]

      nonorm_sub_dir = os.path.join(algorithm, protocol, 'nonorm')
      ztnorm_sub_dir = os.path.join(algorithm, protocol, 'ztnorm')

      # collect the resulting files
      if os.path.exists(os.path.join(result_dir, nonorm_sub_dir, 'scores-dev')):
        result_dev.append(os.path.join(nonorm_sub_dir, 'scores-dev'))
        legends.append(algorithm)

        if has_eval and os.path.exists(os.path.join(result_dir, nonorm_sub_dir, 'scores-eval')):
          result_eval.append(os.path.join(nonorm_sub_dir, 'scores-eval'))

        if has_zt_norm:
          if os.path.exists(os.path.join(result_dir, ztnorm_sub_dir, 'scores-dev')):
            result_zt_dev.append(os.path.join(ztnorm_sub_dir, 'scores-dev'))
          if has_eval and os.path.exists(os.path.join(result_dir, ztnorm_sub_dir, 'scores-eval')):
            result_zt_eval.append(os.path.join(ztnorm_sub_dir, 'scores-eval'))

    # check if we have found some results
    if not result_dev and not args.dry_run:
      logger.warn("No result files were detected -- skipping evaluation.")
      return

    # call the evaluate script
    base_command = ['./bin/evaluate.py', '--directory', result_dir, '--legends'] + legends
    if 'EER' in args.evaluate:
      base_command += ['--criterion', 'EER']
    elif 'HTER' in args.evaluate:
      base_command += ['--criterion', 'HTER']
    if 'ROC' in args.evaluate:
      base_command += ['--roc', 'ROCxxx.pdf']
    if 'DET' in args.evaluate:
      base_command += ['--det', 'DETxxx.pdf']
    if 'CMC' in args.evaluate:
      base_command += ['--cmc', 'CMCxxx.pdf']
    if 'RR' in args.evaluate:
      base_command += ['--rr']
    if args.verbose:
      base_command += ['-' + 'v'*args.verbose]

    # first, run the nonorm evaluation
    if result_zt_dev:
      command = [cmd.replace('xxx','_dev') for cmd in base_command]
    else:
      command = [cmd.replace('xxx','') for cmd in base_command]
    command += ['--dev-files'] + result_dev
    if result_eval:
      command += ['--eval-files'] + result_eval

    logger.info("Executing command:\n%s", bob.bio.base.tools.command_line(command))
    if not args.dry_run:
      subprocess.call(command)

    # now, also run the ZT norm evaluation, if available
    if result_zt_dev:
      command = [cmd.replace('xxx','_eval') for cmd in base_command]
      command += ['--dev-files'] + result_zt_dev
      if result_zt_eval:
        command += ['--eval-files'] + result_zt_eval

      logger.info("Executing command:\n%s", bob.bio.base.tools.command_line(command))
      if not args.dry_run:
        subprocess.call(command)
