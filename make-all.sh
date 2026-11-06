#!/usr/bin/env bash
# Пересобирает всё: три отдельных PDF по видам вкладышей и общий print-all.pdf
# с плотной укладкой для печати.
#
#   ./make-all.sh
set -euo pipefail
cd "$(dirname "$0")"

./make-cards.py       # 14 вкладышей меню в рамку Front: рус + каз
./make-profile.py     # 7 боковин подставки с пейзажем
./make-tips.py        # 7 боковин «на чай» с Kaspi QR

echo
./make-print.py       # всё вместе, плотно: треугольники через один перевёрнуты
