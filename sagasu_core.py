#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 13 14:48:45 2020
@author: Christian M. Orr
"""

import os
import re
import pandas as pd
from matplotlib.patches import Ellipse
from sklearn.mixture import BayesianGaussianMixture as bgm
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import math
import pickle
from sklearn.cluster import DBSCAN
import heapq
from mpl_toolkits.mplot3d import Axes3D
import shutil
from pathlib import Path
import subprocess
import time
from tqdm import tqdm

sns.set()


def get_input():
    projname = input("Name of project (SHELX prefix): ")
    fa_path = input("Path to SHELXC outputs: ")
    highres = int(10 * float(input("High resolution cutoff for grid: ")))
    lowres = int(10 * float(input("Low resolution cutoff for grid: ")))
    highsites = int(input("Maximum number of sites to search: "))
    lowsites = int(input("Minimum number of sites to search: "))
    ntry = int(input("Number of trials: "))
    clust = str(input("Run on (c)luster or (l)ocal machine? c/l ")).lower()
    clusteranalysis = str("Run cluster analysis after (time consuming)? y/n ").lower()
    insin = os.path.join(fa_path, projname + "_fa.ins")
    hklin = os.path.join(fa_path, projname + "_fa.hkl")
    writepickle(
        projname,
        lowres,
        highres,
        lowsites,
        highsites,
        ntry,
        clusteranalysis,
        clust,
        insin,
        hklin,
    )


def writepickle(
    projname,
    lowres,
    highres,
    lowsites,
    highsites,
    ntry,
    clusteranalysis,
    clust,
    insin,
    hklin,
):
    with open("inps.pkl", "wb") as f:
        pickle.dump(
            [
                projname,
                lowres,
                highres,
                lowsites,
                highsites,
                ntry,
                clusteranalysis,
                clust,
                insin,
                hklin,
            ],
            f,
        )


def readpickle(
    projname,
    lowres,
    highres,
    lowsites,
    highsites,
    ntry,
    clusteranalysis,
    clust,
    insin,
    hklin,
):
    with open("inps.pkl", "rb") as f:
        (
            [
                projname,
                lowres,
                highres,
                lowsites,
                highsites,
                ntry,
                clusteranalysis,
                clust,
                insin,
                hklin,
            ]
        ) = pickle.load(f)


def qstat_progress(lowres, highres, lowsites, highsites):
    runs = (((lowres - 1) - highres)) * (highsites - lowsites)
    q = subprocess.Popen("qstat", stdout=subprocess.PIPE)
    q = len(q.stdout.read())
    print("")
    pbar = tqdm(desc="Jobs finished", total=int(runs), dynamic_ncols=True)
    while q > 2:
        t = subprocess.Popen("qstat", stdout=subprocess.PIPE)
        q = len(t.stdout.readlines())
        l = runs - (q - 2)
        pbar.n = int(l)
        pbar.refresh()
        time.sleep(2)
    else:
        print("\nDone processing, moving on to analysis")


def shelx_write(projname):
    shelxjob = open("shelxd_job.sh", "w")
    shelxjob.write("module load shelx\n")
    shelxjob.write("shelxd " + projname + "_fa")
    shelxjob.close()
    os.chmod("shelxd_job.sh", 0o775)


def replace(file, pattern, subst):
    file_handle = open(file, "r")
    file_string = file_handle.read()
    file_handle.close()
    file_string = re.sub(pattern, subst, file_string)
    file_handle = open(file, "w")
    file_handle.write(file_string)
    file_handle.close()


def run_sagasu_proc(
    pro_or_ana,
    projname,
    highres,
    lowres,
    highsites,
    lowsites,
    insin,
    hklin,
    path,
    ntry,
    clust,
):
    if pro_or_ana == "p":
        os.chdir(path)
        Path(projname).mkdir(parents=True, exist_ok=True)
        i = highres
        if clust == 'l':
            tot = ((lowres - highres) * ((highsites + 1) - lowsites))
            pbar = tqdm(desc="SHELXD", total=tot, dynamic_ncols=True)
        while not (i >= lowres):
            Path(os.path.join(projname, str(i))).mkdir(parents=True, exist_ok=True)
            i2 = i / 10
            j = highsites
            while not (j <= (lowsites - 1)):
                os.makedirs(os.path.join(projname, str(i), str(j)), exist_ok=True)
                shutil.copy2(insin, (os.path.join(projname, str(i), str(j))))
                shutil.copy2(hklin, (os.path.join(projname, str(i), str(j))))
                shutil.copy2("shelxd_job.sh", (os.path.join(projname, str(i), str(j))))
                workpath = os.path.join(path, projname, str(i), str(j))
                f = os.path.join(path, projname, str(i), str(j), projname + "_fa.ins")
                replace(f, "FIND", "FIND " + str(j) + "\n")
                replace(f, "SHEL", "SHEL 999 " + str(i2) + "\n")
                replace(f, "NTRY", "NTRY " + str(ntry) + "\n")
                if clust == "l":
                    os.chdir(workpath)
                    shelxdrun = subprocess.run(
                        ["shelxd", projname + '_fa'], stdout=subprocess.PIPE
                    )
                    #print("returncode: ", shelxdrun.returncode)
                    #print(shelxdrun.stdout.decode("utf-8"))
                    pbar.update(1)
                    pbar.refresh()
                    os.chdir(path)
                elif clust == "c":
                    os.system(
                        "cd "
                        + workpath
                        + "; qsub -P i23 -q low.q -l h_vmem=5G -N sag_"
                        + str(i)
                        + "_"
                        + str(j)
                        + " -pe smp 40-10 -cwd ./shelxd_job.sh"
                    )
                else:
                    print("error in input...")
                j = j - 1
            i = i + 1


def cleanup_prev(path, projname, highres, lowres, highsites, lowsites):
    resultspath = os.path.join(path, projname + "_results")
    if os.path.exists(resultspath):
        shutil.rmtree(resultspath)
    if not os.path.exists(projname + "_results"):
        os.mkdir(path + "/" + projname + "_results")
    figspath = os.path.join(path, projname + "_figures")
    if os.path.exists(figspath):
        shutil.rmtree(figspath)
    if not os.path.exists(projname + "_figures"):
        os.mkdir(path + "/" + projname + "_figures")
    i = highres
    while not (i >= lowres):
        j = highsites
        while not (j <= (lowsites - 1)):
            lstfile = os.path.join(
                path,
                projname + "/" + str(i) + "/" + str(j) + "/" + projname + "_fa.lst",
            )
            results(lstfile, path, projname, i, j)
            j = j - 1
        i = i + 1


def results(filename, path, projname, i, j):
    with open(filename, "r") as file:
        filedata = file.read()
        filedata = filedata.replace("/", " ")
        filedata = filedata.replace(",", " ")
        filedata = filedata.replace("CC", "")
        filedata = filedata.replace("All", "")
        filedata = filedata.replace("Weak", "")
        filedata = filedata.replace("CFOM", "")
        filedata = filedata.replace("best", "")
        filedata = filedata.replace("PATFOM", "")
        filedata = filedata.replace("CPU", "")
    with open(filename, "w") as file:
        file.write(filedata)
    with open(filename, "r") as infile, open(
        path + "/" + projname + "_results/" + str(i) + "_" + str(j) + ".csv", "w"
    ) as outfile:
        for line in infile:
            if line.startswith(" Try"):
                outfile.write(",".join(line.split()) + "\n")
    with open(
        path + "/" + projname + "_results/" + str(i) + "_" + str(j) + ".csv", "r"
    ) as f:
        data = f.read()
        with open(
            path + "/" + projname + "_results/" + str(i) + "_" + str(j) + ".csv", "w"
        ) as w:
            w.write(data[:-1])


def run_sagasu_analysis(
    projname, highres, lowres, highsites, lowsites, path, clusteranalysis
):
    if not os.path.exists(projname + "_figures"):
        os.mkdir(projname + "_figures")
    i = highres
    while not (i >= lowres):
        i2 = i / 10
        j = highsites
        while not (j <= (lowsites - 1)):
            print("Results for " + str(i2) + "Å, " + str(j) + " sites:")
            csvfile = os.path.join(
                path, projname + "_results/" + str(i) + "_" + str(j) + ".csv"
            )
            numbers = str(i) + "_" + str(j)
            if clusteranalysis == "y":
                print("***Bayesian Gaussian Mixture Analysis***")
                clustering_distance(projname, path, csvfile, numbers, i, j)
                print("***DBSCAN Analysis***")
                analysis(path, projname, csvfile, numbers, i, j)
                print("***Generating Hexplots***")
                analysis_2(path, projname, csvfile, numbers, i, j)
            else:
                print("No cluster analysis requested")
            print("***Outlier Analysis***")
            ccalloutliers(path, projname, csvfile, i, j)
            ccweakoutliers(path, projname, csvfile, i, j)
            j = j - 1
        i = i + 1


def for_ML_analysis(
    projname, highres, lowres, highsites, lowsites, path, clusteranalysis
):
    if not os.path.exists(projname + "_figures"):
        os.mkdir(projname + "_figures")
    i = highres
    while not (i >= lowres):
        i2 = i / 10
        j = highsites
        while not (j <= (lowsites - 1)):
            print("Results for " + str(i2) + "Å, " + str(j) + " sites:")
            csvfile = os.path.join(
                path, projname + "_results/" + str(i) + "_" + str(j) + ".csv"
            )
            numbers = str(i) + "_" + str(j)
            if clusteranalysis == "y":
                print("***Generating Hexplots***")
                plot_for_ML(path, projname, csvfile, numbers, i, j)
            else:
                print("No cluster analysis requested")
            print("***Outlier Analysis***")
            ccalloutliers(path, projname, csvfile, i, j)
            ccweakoutliers(path, projname, csvfile, i, j)
            j = j - 1
        i = i + 1


def plot_for_ML(path, projname, filename, nums, a_res, a_sites):
    df = pd.read_csv(
        filename,
        sep=",",
        names=["linebeg", "TRY", "CPUNO", "CCALL", "CCWEAK", "CFOM", "BEST", "PATFOM"],
    )
    ccallweak = df[["CCALL", "CCWEAK"]]
    plt.scatter(df["CCALL"], df["CCWEAK"], marker="o")
    plt.axis("off")
    plt.draw()
    ccallvsccweak = plt.gcf()
    ccallvsccweak.savefig(
        path + "/" + projname + "_figures/" + projname + "_" + nums + ".png",
        dpi=500,
        bbox_inches=0,
    )
    ccallvsccweak.clear()
    plt.close(ccallvsccweak)


def draw_ellipse(position, covariance, ax=None, **kwargs):
    """Draw an ellipse with a given position and covariance"""
    ax = ax or plt.gca()
    # Convert covariance to principal axes
    if covariance.shape == (2, 2):
        U, s, Vt = np.linalg.svd(covariance)
        angle = np.degrees(np.arctan2(U[1, 0], U[0, 0]))
        width, height = 2 * np.sqrt(s)
    else:
        angle = 0
        width, height = 2 * np.sqrt(covariance)
    # Draw the Ellipse
    for nsig in range(1, 4):
        ax.add_patch(Ellipse(position, nsig * width, nsig * height, angle, **kwargs))


def plot_gmm(projname, path, gmm, X, n_init, nums, label=True, ax=None):
    ax = ax or plt.gca()
    labels = gmm.fit(X).predict(X)
    if label:
        ax.scatter(X[:, 0], X[:, 1], c=labels, s=40, cmap="viridis", zorder=2)
    else:
        ax.scatter(X[:, 0], X[:, 1], s=40, zorder=2)
    w_factor = 0.2 / gmm.weights_.max()
    for pos, covar, w in zip(gmm.means_, gmm.covariances_, gmm.weights_):
        draw_ellipse(pos, covar, alpha=w * w_factor)
    if gmm.converged_ is True:
        print("Clustering converged after " + str(gmm.n_iter_) + " iterations")
    if gmm.converged_ is False:
        print("Clustering did not converge after " + str(n_init) + " iterations")
    print(
        str(round((gmm.weights_[0]) * 100, 1))
        + "% in first cluster, "
        + str(round((gmm.weights_[1]) * 100, 1))
        + "% in second cluster"
    )
    meanchange = np.vstack((gmm.means_, gmm.mean_prior_))
    dist_c = math.sqrt(
        ((abs((gmm.means_[0][0]) - (gmm.means_[1][0]))) ** 2)
        + ((abs((gmm.means_[0][1]) - (gmm.means_[1][1]))) ** 2)
    )
    print("Distance between clusters = " + str(dist_c))
    separation = open(projname + "_results/clusterseparations.csv", "a")
    separation.write(
        str(meanchange[0])
        + ","
        + str(meanchange[1])
        + ","
        + str(meanchange[2])
        + ","
        + str(dist_c)
        + ","
        + str(round((gmm.weights_[0]) * 100, 1))
        + ","
        + str(round((gmm.weights_[1]) * 100, 1))
        + "\n"
    )
    ax = plt.gcf()
    ax.savefig(path + "/" + projname + "_figures/" + nums + "_clsdst.png", dpi=300)
    ax.clear()
    plt.close(ax)


def clustering_distance(projname, path, csvfile, nums, i, j):
    df = pd.read_csv(
        csvfile,
        sep=",",
        names=["linebeg", "TRY", "CPUNO", "CCALL", "CCWEAK", "CFOM", "BEST", "PATFOM"],
    )
    arr = df[["CCALL", "CCWEAK"]].to_numpy()
    cmean = arr.mean(axis=0)
    csd = arr.std(axis=0)
    outliermask = ((arr[:, 0]) > (cmean[0] - (2 * csd[0]))) & (
        (arr[:, 1]) > (cmean[1] - (2 * csd[1]))
    )
    arr_out = arr[outliermask]
    ni = 1000
    gmm = bgm(
        n_components=2,
        covariance_type="full",
        max_iter=ni,
        init_params="kmeans",
        tol=1e-6,
    )
    plot_gmm(projname, path, gmm, arr, ni, nums)


def analysis(path, projname, filename, nums, a_res, a_sites):
    df = pd.read_csv(
        filename,
        sep=",",
        names=["linebeg", "TRY", "CPUNO", "CCALL", "CCWEAK", "CFOM", "BEST", "PATFOM"],
    )
    ccallweak = df[["CCALL", "CCWEAK"]]
    clustr = DBSCAN(eps=0.7, min_samples=1, n_jobs=-1).fit(ccallweak)
    labels = len(set(clustr.labels_))
    print("DBSCAN found " + str(labels) + " cluster(s)")
    plt.scatter(
        df["CCALL"],
        df["CCWEAK"],
        c=clustr.labels_.astype(float),
        marker="+",
        s=50,
        alpha=0.5,
    )
    plt.xlabel("CCALL")
    plt.ylabel("CCWEAK")
    plt.title("Resolution: " + str(a_res / 10) + "Å , Sites: " + str(a_sites))
    plt.draw()
    ccallvsccweak = plt.gcf()
    ccallvsccweak.savefig(path + "/" + projname + "_figures/" + nums + ".png", dpi=300)
    ccallvsccweak.clear()
    plt.close(ccallvsccweak)


def analysis_2(path, projname, filename, nums, a_res, a_sites):
    df = pd.read_csv(
        filename,
        sep=",",
        names=["linebeg", "TRY", "CPUNO", "CCALL", "CCWEAK", "CFOM", "BEST", "PATFOM"],
    )
    sns.jointplot(x=df["CCALL"], y=df["CCWEAK"], kind="hex", space=0)
    plt.draw()
    snsplot = plt.gcf()
    snsplot.savefig(
        path + "/" + projname + "_figures/" + nums + "_hexplot.png", dpi=300
    )
    snsplot.clear()
    plt.close(snsplot)


def ccalloutliers(path, projname, filename, resolution, sitessearched):
    df = pd.read_csv(
        filename,
        sep=",",
        names=["linebeg", "TRY", "CPUNO", "CCALL", "CCWEAK", "CFOM", "BEST", "PATFOM"],
    )
    pd.DataFrame.drop(df, labels="linebeg", axis=1, inplace=True)
    median = df["CCALL"].median()
    arr = df[["CCALL", "CCWEAK"]].to_numpy()
    cmean = arr.mean(axis=0)
    csd = arr.std(axis=0)
    outliermask = ((arr[:, 0]) > (cmean[0] - (2 * csd[0]))) & (
        (arr[:, 1]) > (cmean[1] - (2 * csd[1]))
    )
    arr = arr[outliermask]
    mad = np.median(np.sqrt((arr[:, 0] - median) ** 2))
    ccallmax = heapq.nlargest(3, arr[:, 0])
    ccallmad = arr[:, 0] - median
    mad10 = sum(i > 10 * mad for i in ccallmad)
    mad9 = sum(i > 9 * mad for i in ccallmad)
    mad8 = sum(i > 8 * mad for i in ccallmad)
    mad7 = sum(i > 7 * mad for i in ccallmad)
    mad6 = sum(i > 6 * mad for i in ccallmad)
    mad5 = sum(i > 5 * mad for i in ccallmad)
    print("number of CCall with CCall - median > 10 * MAD = " + str(mad10))
    print("number of CCall with CCall - median >  9 * MAD = " + str(mad9))
    print("number of CCall with CCall - median >  8 * MAD = " + str(mad8))
    print("number of CCall with CCall - median >  7 * MAD = " + str(mad7))
    print("number of CCall with CCall - median >  6 * MAD = " + str(mad6))
    print("number of CCall with CCall - median >  5 * MAD = " + str(mad5))
    print("Three largest CCall values: " + str(ccallmax))
    allmad = open(projname + "_results/ccall.csv", "a")
    allmad.write(
        str(int(resolution) / 10)
        + ","
        + str(sitessearched)
        + ","
        + str(mad5)
        + ","
        + str(mad6)
        + ","
        + str(mad7)
        + ","
        + str(mad8)
        + ","
        + str(mad9)
        + ","
        + str(mad10)
        + "\n"
    )
    allmad.close()


def ccweakoutliers(path, projname, filename, resolution, sitessearched):
    df = pd.read_csv(
        filename,
        sep=",",
        names=["linebeg", "TRY", "CPUNO", "CCALL", "CCWEAK", "CFOM", "BEST", "PATFOM"],
    )
    pd.DataFrame.drop(df, labels="linebeg", axis=1, inplace=True)
    median = df["CCWEAK"].median()
    arr = df[["CCALL", "CCWEAK"]].to_numpy()
    cmean = arr.mean(axis=0)
    csd = arr.std(axis=0)
    outliermask = ((arr[:, 0]) > (cmean[0] - (2 * csd[0]))) & (
        (arr[:, 1]) > (cmean[1] - (2 * csd[1]))
    )
    arr = arr[outliermask]
    mad = np.median(np.sqrt((arr[:, 1] - median) ** 2))
    ccweakmax = heapq.nlargest(3, arr[:, 1])
    ccweakmad = arr[:, 1] - median
    mad10 = sum(i > 10 * mad for i in ccweakmad)
    mad9 = sum(i > 9 * mad for i in ccweakmad)
    mad8 = sum(i > 8 * mad for i in ccweakmad)
    mad7 = sum(i > 7 * mad for i in ccweakmad)
    mad6 = sum(i > 6 * mad for i in ccweakmad)
    mad5 = sum(i > 5 * mad for i in ccweakmad)
    print("number of CCweak with CCweak - median > 10 * MAD = " + str(mad10))
    print("number of CCweak with CCweak - median >  9 * MAD = " + str(mad9))
    print("number of CCweak with CCweak - median >  8 * MAD = " + str(mad8))
    print("number of CCweak with CCweak - median >  7 * MAD = " + str(mad7))
    print("number of CCweak with CCweak - median >  6 * MAD = " + str(mad6))
    print("number of CCweak with CCweak - median >  5 * MAD = " + str(mad5))
    print("Three largest CCweak values: " + str(ccweakmax))
    print("")
    allmad = open(projname + "_results/ccweak.csv", "a")
    allmad.write(
        str(int(resolution) / 10)
        + ","
        + str(sitessearched)
        + ","
        + str(mad5)
        + ","
        + str(mad6)
        + ","
        + str(mad7)
        + ","
        + str(mad8)
        + ","
        + str(mad9)
        + ","
        + str(mad10)
        + "\n"
    )
    allmad.close()


def tophits(projname, path):
    df = pd.read_csv(
        projname + "_results/ccall.csv",
        sep=",",
        names=["res", "sites", "mad5", "mad6", "mad7", "mad8", "mad9", "mad10"],
    )
    df["score"] = (
        (df["mad5"] * 1)
        + (df["mad6"] * 4)
        + (df["mad7"] * 8)
        + (df["mad8"] * 32)
        + (df["mad9"] * 128)
        + (df["mad10"] * 512)
    )
    df.sort_values(by=["score"], ascending=False, inplace=True)
    top = df[["res", "sites", "score"]]
    top = df.head(10)
    top = top.reset_index(drop=True)
    print(
        """
    Here are the top 10 hits:

    """
    )
    print(top)
    ax = plt.axes(projection="3d")
    ax.plot_trisurf(
        df["res"], df["sites"], df["score"], cmap="viridis", edgecolor="none"
    )
    madplot = plt.gcf()
    madplot.savefig(projname + "_figures/mad.png", dpi=600)
    (firstres, firstsites, secondres, secondsites) = (
        top.iloc[[0], [0]].values[0],
        top.iloc[[0], [1]].values[0],
        top.iloc[[1], [0]].values[0],
        top.iloc[[1], [1]].values[0],
    )
    (firstres, firstsites, secondres, secondsites) = (
        ((firstres * 10).astype(np.int)).item(0),
        (firstsites.astype(np.int)).item(0),
        ((secondres * 10).astype(np.int)).item(0),
        (secondsites.astype(np.int)).item(0),
    )
    with open(
        path
        + "/"
        + projname
        + "/"
        + str(firstres)
        + "/"
        + str(firstsites)
        + "/"
        + projname
        + "_fa.res",
        "r",
    ) as infile:
        for line in infile:
            if line.startswith("TITL"):
                words = line.split()
                sg = words[-1]
    print("The space group has been identified as " + sg)
    phenixemma = open("phenix_emma.sh", "w")
    phenixemma.write("module load phenix \n")
    phenixemma.write(
        "phenix.emma "
        + path
        + "/"
        + projname
        + "/"
        + str(firstres)
        + "/"
        + str(firstsites)
        + "/"
        + projname
        + "_fa.pdb "
        + path
        + "/"
        + projname
        + "/"
        + str(secondres)
        + "/"
        + str(secondsites)
        + "/"
        + projname
        + "_fa.pdb --tolerance=6 --space_group="
        + sg
        + " 2>&1 | tee -a sagasu.log"
    )
    phenixemma.close()
    os.chmod("phenix_emma.sh", 0o775)
    os.system("./phenix_emma.sh")


def write_analysis_file(pro_or_ana, statusofrun):
    shelxjob = open("wait.sh", "w")
    shelxjob.write("module load python/3 \n")
    shelxjob.write(
        "/home/i23user/bin/shelxgrid/sagasu_analysis 2>&1 | tee -a sagasu.log"
    )
    shelxjob.close()
    os.chmod("wait.sh", 0o775)
    if pro_or_ana == "a":
        os.system("./wait.sh")
    if pro_or_ana == "p":
        os.system(
            "qsub "
            + statusofrun
            + " -N sagasuanalysis -P i23 -q low.q -l h_vmem=4G -pe smp 20 -cwd ./wait.sh"
        )
