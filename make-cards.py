#!/usr/bin/env python3
"""Генератор PDF с QR-карточками на столики для печати и ламинации.

Делает всё сам: QR-коды (qrencode) -> HTML -> PDF (headless Chrome).

    ./make-cards.py                      # столики 1-7, по 2 карточки
    ./make-cards.py --tables 12           # столики 1-12
    ./make-cards.py --tables 7 --copies 3 # по 3 карточки на столик
    ./make-cards.py --title "Меню"        # другое слово на карточке

Нужны qrencode и google-chrome (или chromium).
"""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile

BASE_URL = "https://makhnanov.github.io/kafe-menu/"
HERE = pathlib.Path(__file__).resolve().parent

# Размеры под A4 (21 x 29.7 см): ячейка 6 x 9 см -> сетка 3 x 3
CELL_W, CELL_H = 6, 9
COLS, ROWS = 3, 3
PER_PAGE = COLS * ROWS
MARGIN_X = (21 - COLS * CELL_W) / 2      # 1.5 см
MARGIN_Y = (29.7 - ROWS * CELL_H) / 2    # 1.35 см


def tool(*names):
    """Первая найденная в системе программа из списка."""
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    sys.exit(f"не найдено: {' / '.join(names)}")


def qr_svg(url, workdir, name):
    """QR в виде инлайнового SVG без фиксированных размеров."""
    out = workdir / f"{name}.svg"
    subprocess.run(
        [tool("qrencode"), "-t", "SVG", "-m", "0", "-s", "10", "-l", "H",
         "-o", str(out), url],
        check=True,
    )
    raw = out.read_text(encoding="utf-8")
    raw = re.sub(r"<\?xml.*?\?>", "", raw, flags=re.S)
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    raw = re.sub(r'\swidth="[^"]*"', "", raw, count=1)
    raw = re.sub(r'\sheight="[^"]*"', "", raw, count=1)
    return raw.strip()


def card_html(n, qr, title):
    return f"""
    <div class="cell">
      <div class="card">
        <div class="frame">
          <div class="brand">{title}</div>
          <div class="rule"><span>&#10022;</span></div>
          <div class="qr">{qr}</div>
          <div class="table">Столик <b>№{n}</b></div>
          <div class="hint">Наведите камеру телефона</div>
        </div>
      </div>
    </div>"""


def build_html(tables, copies, title, base_url, workdir):
    qrs = {n: qr_svg(f"{base_url}?table={n}", workdir, f"t{n}") for n in tables}
    cards = [n for n in tables for _ in range(copies)]
    pages = [cards[i:i + PER_PAGE] for i in range(0, len(cards), PER_PAGE)]

    body = ""
    for idx, page in enumerate(pages):
        filler = PER_PAGE - len(page) if idx == len(pages) - 1 else 0
        body += '<div class="sheet">' + "".join(card_html(n, qrs[n], title) for n in page)
        body += '<div class="cell empty"></div>' * filler
        body += "</div>\n"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>QR-карточки на столики</title>
<style>
  @page {{ size: A4; margin: {MARGIN_Y}cm {MARGIN_X}cm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #fff; }}

  .sheet {{
    width: {COLS * CELL_W}cm; height: {ROWS * CELL_H}cm;
    display: grid;
    grid-template-columns: repeat({COLS}, {CELL_W}cm);
    grid-template-rows: repeat({ROWS}, {CELL_H}cm);
    page-break-after: always;
  }}
  .sheet:last-child {{ page-break-after: auto; }}

  /* линия реза */
  .cell {{
    width: {CELL_W}cm; height: {CELL_H}cm;
    outline: 0.2mm dashed #c9c2b4;
    outline-offset: -0.1mm;
    padding: 3mm;
  }}
  .cell.empty {{ outline-color: #e8e4dc; }}

  .card {{
    width: 100%; height: 100%;
    background: #fdfaf3;
    border: 0.45mm solid #b08a3a;
    border-radius: 2mm;
    padding: 1mm;
  }}
  .frame {{
    width: 100%; height: 100%;
    border: 0.18mm solid #d8c79a;
    border-radius: 1.4mm;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 1.6mm;
    padding: 2.5mm 2mm;
  }}

  .brand {{
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 30pt; line-height: 1;
    letter-spacing: 0.5pt;
    color: #6b4a12;
  }}
  .rule {{
    width: 72%; height: 1px;
    background: linear-gradient(90deg, transparent, #c7ab6a, transparent);
    position: relative;
    margin: 0.4mm 0 1.2mm;
  }}
  .rule span {{
    position: absolute; top: -6.5pt; left: 50%; transform: translateX(-50%);
    background: #fdfaf3; padding: 0 2mm;
    font-size: 8pt; color: #b08a3a;
  }}

  .qr {{ width: 38mm; height: 38mm; }}
  .qr svg {{ width: 100%; height: 100%; display: block; }}

  .table {{
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 12pt; color: #3d3528; margin-top: 1.4mm;
  }}
  .table b {{ color: #6b4a12; font-size: 13.5pt; }}
  .hint {{
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 6.6pt; color: #9a907d; letter-spacing: 0.2pt;
  }}
</style>
</head>
<body>
{body}</body>
</html>"""
    return html, len(cards), len(pages)


def main():
    ap = argparse.ArgumentParser(description="PDF с QR-карточками на столики")
    ap.add_argument("--tables", type=int, default=7, help="сколько столиков (по умолчанию 7)")
    ap.add_argument("--copies", type=int, default=2, help="карточек на столик (по умолчанию 2)")
    ap.add_argument("--title", default="Menu", help="слово на карточке (по умолчанию Menu)")
    ap.add_argument("--url", default=BASE_URL, help="адрес меню")
    ap.add_argument("-o", "--out", default=str(HERE / "qr-cards.pdf"), help="куда сохранить PDF")
    a = ap.parse_args()

    tables = range(1, a.tables + 1)
    out = pathlib.Path(a.out).resolve()

    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        html, n_cards, n_pages = build_html(tables, a.copies, a.title, a.url, workdir)
        page = workdir / "cards.html"
        page.write_text(html, encoding="utf-8")

        subprocess.run(
            [tool("google-chrome", "chromium", "chromium-browser"),
             "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", f"--print-to-pdf={out}", page.as_uri()],
            check=True, capture_output=True,
        )

    print(f"карточек: {n_cards}, листов A4: {n_pages} -> {out}")
    print("печатать в масштабе 100% («фактический размер»), иначе 6×9 см поедет")


if __name__ == "__main__":
    main()
