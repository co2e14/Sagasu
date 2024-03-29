#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Chris
"""
import sagasu_core
import os
from multiprocessing import Pool
from halo import Halo
import time


path = os.getcwd()
print("You are here:", path)
pool = Pool(os.cpu_count() - 1)
print("Using ", str(os.cpu_count() - 1), "CPU cores")
pro_or_ana = str(
    input(
        "Would you like to run (p)rocessing and analysis or just (a)nalysis: "
    ).lower()
)


if pro_or_ana == "p":
    run = sagasu_core.core()
    projname, fa_path, highres, lowres, highsites, lowsites, ntry = run.get_input()
    run.writepickle()
    if os.path.exists(os.path.join(path, "inps.pkl")):
        with Halo(
            text="\nPrepping Jobs",
            text_color="green",
            spinner="pipe",
        ):
            run.readpickle()
            run.prasa_prep()
            run.shelxd_prep()
        with Halo(
            text="\nSubmitting jobs", text_color="green", spinner="monkey",
        ):
            run.run_sagasu_proc()
        with Halo(
            text="\nJobs are running, please be patient and watch the shark",
            text_color="green",
            spinner="shark",
        ):
            run.drmaa2_check()
    else:
        pass

if pro_or_ana == "a" or "p":
    run = sagasu_core.core()
    if os.path.exists(os.path.join(path, "inps.pkl")):
        run.readpickle()
        to_run, to_run_prasa = run.cleanup_prev()
        with Halo(
            text="\nPulling out the important stuff",
            text_color="green",
            spinner="dots12",
        ):
            pool.starmap(run.results, to_run)
            #pool.starmap(run.prasa_results, to_run_prasa)
        #run.prasa_results_concurrent()
        ccoutliers_torun = run.run_sagasu_analysis()
        with Halo(text="\nLooking for outliers", text_color="green", spinner="toggle"):
            pool.starmap(run.ccalloutliers, ccoutliers_torun)
            pool.starmap(run.ccweakoutliers, ccoutliers_torun)
            pool.starmap(run.CFOM_PATFOM_analysis, ccoutliers_torun)
            #to_run_emma = run.get_filenames_for_emma()
            #emma_results = pool.starmap(run.run_emma, to_run_emma) # uncomment for local
            #run.run_emma_cluster(to_run_emma) # uncomment for cluster
            #run.emma_correlation_plot(emma_results) # uncomment for local
            run.vectoroutliers()
            run.tophits()
        with Halo(
            text="\nGenerating pretty pictures", text_color="green", spinner="pong"
        ):
            to_run_ML = run.for_ML_analysis()
            pool.starmap(run.plot_for_ML, to_run_ML)
            run.writehtml()
        print("\nRun 'firefox sagasu.html' to view results")
    else:
        print("No previous run found!")
