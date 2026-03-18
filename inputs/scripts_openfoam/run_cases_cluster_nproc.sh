#!/bin/bash
#SBATCH --job-name=foam
#SBATCH --ntasks=32
#SBATCH --mem=4GB
#SBATCH --time=24:00:00
#SBATCH --partition=geocean

formated_case=$(printf "%04d" $SLURM_ARRAY_TASK_ID)
route="/lustre/geocean/WORK/users/alonsoap/personal/estancia_NUS_2026/HyCFD/outputs/openfoam_nproc_test/$formated_case"
cd $route

. /nfs/software/geocean/spack/share/spack/setup-env.sh
spack load gcc@10.5.0
spack load /c6qywm7
spack load gsl
export GSL_PREFIX=$(spack location -i gsl)
export LD_LIBRARY_PATH=$GSL_PREFIX/lib:$LD_LIBRARY_PATH

. /nfs/software/geocean/NEW/OpenFOAM-v1912/etc/bashrc

decomposePar > decompose.log 2>&1
mpirun -np $SLURM_ARRAY_TASK_ID waveFoam -parallel > waveFoam.log 2>&1
