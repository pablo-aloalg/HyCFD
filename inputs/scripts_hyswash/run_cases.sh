#!/bin/bash
#SBATCH --job-name=swash
#SBATCH --ntasks=1
#SBATCH --mem=4GB
#SBATCH --time=24:00:00
#SBATCH --partition=geocean

formated_case=$(printf "%04d" $SLURM_ARRAY_TASK_ID)
route="/lustre/geocean/WORK/users/alonsoap/personal/estancia_NUS_2026/HyCFD/outputs/swash_molokai_dynamic_cases/$formated_case"

launchSwash.sh --case-dir $route
