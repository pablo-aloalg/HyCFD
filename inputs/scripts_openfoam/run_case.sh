#!/bin/bash

CASE_DIR="$1"

source /opt/OpenFOAM/OpenFOAM-v1912/etc/bashrc
cd "$CASE_DIR" 

decomposePar #Decompose per processor
mpirun -np 8 waveFoam -parallel > waveFoam.log 2>&1
