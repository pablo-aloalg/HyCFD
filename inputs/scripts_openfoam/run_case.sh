#!/bin/bash

CASE_DIR="$1"

source /opt/OpenFOAM/OpenFOAM-v1912/etc/bashrc
cd "$CASE_DIR" 

mpirun -np 8 waveFoam -parallel
