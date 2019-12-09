#!/bin/sh

outfile="makeyear.csv"
echo "" > ${outfile}

for v in `seq 66` ; do
  y=`expr $v + 1953`
  printf "%d,%d,%d\n" $v $y $v >> ${outfile}
done
