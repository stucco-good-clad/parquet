#!/bin/bash
while true; do
  echo -e "\033[H\033[2J"
  echo "=== $(date) ==="
  echo ""
  echo "--- CPU ---"
  mpstat 1 1 2>/dev/null | tail -1 || top -bn1 | grep "Cpu(s)"
  echo ""
  echo "--- RAM ---"
  free -h
  echo ""
  echo "--- DISK ---"
  df -h / ./hf 2>/dev/null
  echo ""
  echo "--- FUSE MOUNT ---"
  du -sh ./hf/torrent-data/ 2>/dev/null || echo "(no torrent-data yet)"
  ls -lhS ./hf/torrent-data/aa_derived_mirror_metadata_20260208/ 2>/dev/null | head -20 || echo "(no files yet)"
  sleep 1
done
