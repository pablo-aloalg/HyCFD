#!/bin/bash
#SBATCH --job-name=swash
#SBATCH --ntasks=1
#SBATCH --mem=4GB
#SBATCH --time=24:00:00
<<<<<<< HEAD
#SBATCH --partition=geocean
=======
#SBATCH --partition=geocean_priority
#sBATCH --exclude=geocean05,geocean06
>>>>>>> origin/main

formated_case=$(printf "%04d" $SLURM_ARRAY_TASK_ID)
route="/nfs/home/geocean/alonsoap/projects/HyCFD/outputs/hyswash_cases/$formated_case"

launchSwash.sh --case-dir $route
