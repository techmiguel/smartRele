set -e
cd /home/user/pcb
N=$1
python3 build_pcb.py /home/user/pcb/$N.kicad_pcb
python3 route.py /home/user/pcb/$N
rm -f $N.ses
timeout 200 xvfb-run -a java -Xmx700m -jar /tmp/fr19.jar -de $N.dsn -do $N.ses -mp 15 > fr_$N.log 2>&1 || true
ls -la $N.ses
timeout 200 python3 finish.py /home/user/pcb/$N
grep -E "^\*\* Found" ${N}_drc.rpt; grep -E "^\[" ${N}_drc.rpt | cut -d']' -f1 | sort | uniq -c | sort -rn
