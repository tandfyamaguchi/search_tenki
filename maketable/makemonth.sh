#!/bin/sh

outfile="makemonth.csv"
echo "" > ${outfile}

for v in `seq 66` ; do

    case "$v" in
	"1" ) m_end=8 ;;
	"4" ) m_end=13 ;;
	* ) m_end=12
    esac

    for m in `seq ${m_end}` ; do
	printf "%d,%d\n" $v $m  >> ${outfile}
    done
    
done
