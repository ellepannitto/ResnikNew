import os
import numpy as np
from scipy.spatial.distance import cosine
import itertools
import tqdm
from multiprocessing import Pool
import functools
import heapq
import gzip


def tuples_generator(nouns_per_verb):
    files = [itertools.combinations(nouns_per_verb[verb], 2) for verb in nouns_per_verb]
    last_tuple = None
    for tuple in heapq.merge(*files):
        if not tuple == last_tuple:
            yield tuple
            last_tuple = tuple

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)

files_dict = {}
def parallel_f(noun_vectors, file_prefix, tup):

    global files_dict

    pid = os.getpid()
    if not pid in files_dict:
        files_dict[pid] = gzip.open(file_prefix+".{}.gzip".format(pid), "wt")
        print(pid, "OPENING FILE", file_prefix+".{}.gzip".format(pid))

    tup_list = filter(lambda x: x is not None, tup)
    for n1, n2 in tup_list:
        print(n1, n2, "{:.4f}".format(1-cosine(noun_vectors[n1], noun_vectors[n2])), file=files_dict[pid])

def compute_measure(input_path, output_path, nouns_file, n_workers):
    global files_dict

    os.makedirs(output_path, exist_ok=True)

    nouns = set()
    with open(nouns_file) as fin:
        for line in fin:
            line = line.strip().split()
            nouns.add(line[0])

    nouns_per_verb = {}
    tot_pairs = {}
    for filename in os.listdir(input_path):
        verb = filename.split(".")[-1]
        print(verb)
        nouns_per_verb[verb] = []
        with open(input_path+filename) as fin:
            for line in fin:
                word = line.strip().split()[0]
                if all(x.isalpha() or x in ["-", "'"] for x in word):
                    nouns_per_verb[verb].append(word)

            nouns_per_verb[verb] = list(sorted(nouns_per_verb[verb]))
            tot_pairs[verb] = (len(nouns_per_verb[verb]) * (len(nouns_per_verb[verb]) - 1)) // 2


    for algo in ["word2vec", "word2vecf"]:
        models_dir = "/extra/DSM/07_models/{}".format(algo)
        for folder in os.listdir(models_dir):
            print("WORKING ON FOLDER: ", folder)
            with open(models_dir + "/" + folder + "/targets_vectors.decoded") as fin_model:
                noun_vectors = {}
                fin_model.readline()
                for line in fin_model:
                    line = line.strip().split()
                    word = line[0]
                    if word in nouns:
                        try:
                            vector = [float(x) for x in line[1:]]
                            noun_vectors[word] = vector
                        except:
                            pass

            min_len = min([len(vector) for vector in noun_vectors.values()])
            print("LEN VECTORS: ", min_len)
            for n in noun_vectors:
                v = noun_vectors[n][-min_len:]
                noun_vectors[n] = np.array(v)

            file_prefix = output_path + algo + "." + folder
            with Pool(n_workers) as p:
                iterator = grouper(tuples_generator(nouns_per_verb), 500000)
                imap_obj = p.imap(functools.partial(parallel_f, noun_vectors, file_prefix), iterator)

                for x in tqdm.tqdm (imap_obj, total=sum(tot_pairs.values()) // 500000) :
                    pass

            for pid in files_dict:
                files_dict[pid].close()
                print(pid, "CLOSING FILE")
                del files_dict[pid]


    for algo in ["SVD"]:
        models_dir = "/extra/DSM/07_models/{}".format(algo)
        for folder in tqdm.tqdm(os.listdir(models_dir)):
            print("WORKING ON FOLDER: ", folder)
            with open(models_dir + "/" + folder + "/counts-ppmi-svd.decoded") as fin_model:
                noun_vectors = {}
                fin_model.readline()
                for line in fin_model:
                    line = line.strip().split()
                    word = line[0]
                    if word in nouns:
                        try:
                            vector = np.array([float(x) for x in line[1:]])
                            noun_vectors[word] = vector
                        except:
                            pass

            min_len = min([len(vector) for vector in noun_vectors.values()])
            print("LEN VECTORS: ", min_len)
            for n in noun_vectors:
                v = noun_vectors[n][-min_len:]
                noun_vectors[n] = np.array(v)

            file_prefix = output_path + algo + "." + folder
            with Pool(n_workers) as p:
                iterator = grouper(tuples_generator(nouns_per_verb), 500000)
                imap_obj = p.imap(functools.partial(parallel_f, noun_vectors, file_prefix), iterator)

                for x in tqdm.tqdm(imap_obj, total=sum(tot_pairs.values()) // 500000):
                    pass

            for pid in files_dict:
                files_dict[pid].close()
                print(pid, "CLOSING FILE")
                del files_dict[pid]
