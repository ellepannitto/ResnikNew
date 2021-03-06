import logging
import itertools
import contextlib
import gzip
import heapq
import os
import functools
import glob
import tqdm
import uuid

from scipy.spatial.distance import cosine
from multiprocessing import Pool

from resnikmeasure.utils import data_utils as dutils

logger = logging.getLogger(__name__)


def tuples_generator(nouns_per_verb):
    files = [itertools.combinations(nouns_per_verb[verb], 2) for verb in nouns_per_verb]
    last_tuple = None
    for tup in heapq.merge(*files):
        if not tup == last_tuple:
            yield tup
            last_tuple = tup


def parallel_f(noun_vectors, file_prefix, tup):

    random_id = uuid.uuid4()
    filename = file_prefix+".{}.gzip".format(random_id)
    with gzip.open(filename, "wt") as fout:
        tup_list = filter(lambda x: x is not None, tup)
        for n1, n2 in tup_list:
            print(n1, n2, "{:.4f}".format(1-cosine(noun_vectors[n1], noun_vectors[n2])), file=fout)


def compute_cosines(input_paths, output_path, nouns_fpath, n_workers, models_filepath):

    nouns = dutils.load_nouns_set(nouns_fpath)
    nouns_per_verb, tot_pairs = dutils.load_nouns_per_verb(input_paths)
    models = dutils.load_models_dict(models_filepath)

    for model_name, model_path in models.items():

        logger.info("loading vectors from {}".format(model_name))

        noun_vectors = dutils.load_vectors(model_path, nouns)

        found = {}
        not_found = {}
        with open(output_path+"coverage.{}".format(model_name), "w") as fout:
            for verb in nouns_per_verb:
                found[verb] = []
                not_found[verb] = []
                for noun in nouns_per_verb[verb]:
                    if noun in noun_vectors:
                        found[verb].append(noun)
                    else:
                        not_found[verb].append(noun)
                tot_pairs[verb] = (len(found[verb]) * (len(found[verb]) - 1)) // 2
                print(verb, "found", len(found[verb]), "not found", len(not_found[verb]), file=fout)

        file_prefix = output_path + model_name
        with Pool(n_workers) as p:
            iterator = dutils.grouper(tuples_generator(found), 5000000)
            imap_obj = p.imap(functools.partial(parallel_f, noun_vectors, file_prefix), iterator)
            for _ in tqdm.tqdm(imap_obj, total=sum(tot_pairs.values())//5000000):
                pass


def merge(dir_path, tup):
    model, files = tup
    logger.info("{} - PROCESSING MODEL {}".format(os.getpid(), model))
    with contextlib.ExitStack() as stack:
        files = [stack.enter_context(gzip.open(fn, "rt")) for fn in files]
        with gzip.open(dir_path+'/{}.merged.gzip'.format(model), 'wt') as f:
            f.writelines(heapq.merge(*files))


def merge_cosines_files(dir_path, models_fpath):

    logger.info("merging process started")

    models = dutils.load_models_dict(models_fpath)
    d = {model_name: glob.glob(dir_path+model_name+"*") for model_name in models}

    with Pool(6) as p:
        for _ in tqdm.tqdm(p.map(functools.partial(merge, dir_path), d.items())):
            pass

    for model_name in d:
        for file in d[model_name]:
            os.remove(file)
