#!/bin/bash

CASE_DIR="$1"

. /nfs/software/geocean/spack/share/spack/setup-env.sh
spack load gcc@10.5.0
spack load /c6qywm7
spack load gsl
export GSL_PREFIX=$(spack location -i gsl)
export LD_LIBRARY_PATH=$GSL_PREFIX/lib:$LD_LIBRARY_PATH

. /nfs/software/geocean/NEW/OpenFOAM-v1912/etc/bashrc

cd "$CASE_DIR" 

setWaveParameters # 3. Set wave parameters 
setWaveField # 4. Initialize wave field in 0/ folder
waveGaugesNProbes # 5. Set up wave gauges and probes 
decomposePar # 6. Decompose per processor