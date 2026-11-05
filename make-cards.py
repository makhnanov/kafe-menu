#!/usr/bin/env python3
"""Генератор PDF с QR-карточками-вкладышами на столики под рамку Front.dxf.

Делает всё сам: QR-коды (qrencode) -> HTML -> PDF (headless Chrome).

    ./make-cards.py                       # столики 1-7, русский + казахский
    ./make-cards.py --langs ru            # только русские
    ./make-cards.py --tables 12           # столики 1-12
    ./make-cards.py --clearance 0         # вкладыш ровно в размер рамки

Русская карточка ведёт на ?table=N, казахская — на ?table=N&lang=kk.

Размеры из Front.dxf. Лист целиком 60.4 x 125.639 мм = лицевая панель
(106.955) + нижняя планка (18.684). Видно только окно 53 x 97 мм в верхней
части: весь текст и QR лежат внутри него с запасом 1.5 мм. Остальное —
губы окна по 3.7 мм и скрытый низ 24.939 мм — печатается пустым: бумага
там нужна, чтобы лист держался и опирался на планку, но смотреть там нечего.

Нужны qrencode и google-chrome (или chromium).
"""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile

BASE_URL = "https://makhnanov.github.io/kafe-menu/"
HERE = pathlib.Path(__file__).resolve().parent

# --- геометрия рамки Front.dxf, мм ---
FRONT_W, FRONT_H = 60.4, 106.9546        # лицевая панель с окном
BOT_H = 18.6843                          # нижняя планка: прячет низ листа и подпирает его
WIN_W, WIN_H = 53.0, 97.0                # окно — единственное, что видно
WIN_L, WIN_T = 3.7, 3.7                  # губы окна слева/справа/сверху
SAFE = 1.5                               # запас внутрь окна, чтобы губа не срезала рисунок

# весь лист = панель + планка; низ уходит внутрь и ничего не показывает
SHEET_W, SHEET_H = FRONT_W, FRONT_H + BOT_H          # 60.4 x 125.639
HIDDEN_B = FRONT_H - WIN_T - WIN_H + BOT_H           # 24.939 — скрытый низ листа

# --- раскладка на A4 (210 x 297 мм) ---
COLS, ROWS = 3, 2
GAP = 5.0                                # зазор между карточками
MARK_OFF, MARK_LEN = 1.2, 2.6            # метки реза в зазоре

TEXTS = {
    "ru": {"brand": "Menu", "table": "Столик", "hint": "Наведите камеру телефона"},
    "kk": {"brand": "Мәзір", "table": "Үстел", "hint": "Телефон камерасын бағыттаңыз"},
}


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


def card_html(n, lang, qr, titles):
    t = dict(TEXTS[lang])
    if titles.get(lang):
        t["brand"] = titles[lang]
    marks = "".join(f'<i class="m {c}"></i>' for c in
                    ("tl h", "tl v", "tr h", "tr v", "bl h", "bl v", "br h", "br v"))
    return f"""
    <div class="cell">{marks}
      <div class="card">
        <div class="win">
          <div class="brand">{t['brand']}</div>
          <div class="rule"><span>&#10022;</span></div>
          <div class="qr">{qr}</div>
          <div class="table">{t['table']} <b>&#8470;{n}</b></div>
          <div class="hint">{t['hint']}</div>
        </div>
        <div class="tag">{n} &middot; {lang.upper()}</div>
      </div>
    </div>"""


def menu_url(base_url, n, lang):
    """Русская карточка — обычный адрес, казахская — с ?lang=kk."""
    url = f"{base_url}?table={n}"
    return url if lang == "ru" else f"{url}&lang={lang}"


def build_html(tables, langs, titles, base_url, clearance, workdir):
    qrs = {(n, l): qr_svg(menu_url(base_url, n, l), workdir, f"t{n}-{l}")
           for n in tables for l in langs}

    # на листе: верхний ряд — первый язык, нижний — второй, те же столики
    cards = []
    for chunk in [tables[i:i + COLS] for i in range(0, len(tables), COLS)]:
        for lang in langs:
            cards += [(n, lang) for n in chunk]
            cards += [None] * (COLS - len(chunk))
    pages = [cards[i:i + COLS * ROWS] for i in range(0, len(cards), COLS * ROWS)]

    body = ""
    for page in pages:
        body += '<div class="sheet">' + "".join(
            '<div class="cell empty"></div>' if c is None
            else card_html(c[0], c[1], qrs[c], titles) for c in page)
        body += "</div>\n"

    c = clearance / 2
    card_w, card_h = SHEET_W - clearance, SHEET_H - clearance
    win_l, win_t = WIN_L - c + SAFE, WIN_T - c + SAFE
    win_w, win_h = WIN_W - 2 * SAFE, WIN_H - 2 * SAFE
    sheet_w = COLS * card_w + (COLS - 1) * GAP
    sheet_h = ROWS * card_h + (ROWS - 1) * GAP
    mar_x, mar_y = (210 - sheet_w) / 2, (297 - sheet_h) / 2

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>QR-вкладыши на столики</title>
<style>
  @page {{ size: A4; margin: {mar_y:.3f}mm {mar_x:.3f}mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #fff; }}

  .sheet {{
    width: {sheet_w:.3f}mm; height: {sheet_h:.3f}mm;
    display: grid;
    grid-template-columns: repeat({COLS}, {card_w:.3f}mm);
    grid-template-rows: repeat({ROWS}, {card_h:.3f}mm);
    gap: {GAP}mm;
    page-break-after: always;
  }}
  .sheet:last-child {{ page-break-after: auto; }}

  .cell {{ position: relative; width: {card_w:.3f}mm; height: {card_h:.3f}mm; }}

  /* метки реза — в зазоре, на самой карточке ничего лишнего */
  .m {{ position: absolute; background: #9a907d; }}
  .m.h {{ width: {MARK_LEN}mm; height: 0.15mm; }}
  .m.v {{ width: 0.15mm; height: {MARK_LEN}mm; }}
  .m.tl.h, .m.bl.h {{ right: 100%; margin-right: {MARK_OFF}mm; }}
  .m.tr.h, .m.br.h {{ left: 100%; margin-left: {MARK_OFF}mm; }}
  .m.tl.v, .m.tr.v {{ bottom: 100%; margin-bottom: {MARK_OFF}mm; }}
  .m.bl.v, .m.br.v {{ top: 100%; margin-top: {MARK_OFF}mm; }}
  .m.tl.h, .m.tr.h {{ top: 0; }}
  .m.bl.h, .m.br.h {{ bottom: 0; }}
  .m.tl.v, .m.bl.v {{ left: 0; }}
  .m.tr.v, .m.br.v {{ right: 0; }}

  /* линия реза по контуру вкладыша — прячется под лип рамки */
  .card {{
    position: relative;
    width: 100%; height: 100%;
    background: #fdfaf3;
    outline: 0.15mm dashed #cfc8ba;
    outline-offset: -0.075mm;
  }}
  .cell.empty {{ }}

  /* рисунок живёт внутри окна рамки */
  .win {{
    position: absolute;
    left: {win_l:.3f}mm; top: {win_t:.3f}mm;
    width: {win_w:.3f}mm; height: {win_h:.3f}mm;
    border: 0.45mm solid #b08a3a;
    border-radius: 2mm;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 2mm;
    padding: 3mm 2mm;
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
    margin: 0.6mm 0 2mm;
  }}
  .rule span {{
    position: absolute; top: -6.5pt; left: 50%; transform: translateX(-50%);
    background: #fdfaf3; padding: 0 2mm;
    font-size: 8pt; color: #b08a3a;
  }}

  .qr {{ width: 42mm; height: 42mm; }}
  .qr svg {{ width: 100%; height: 100%; display: block; }}

  .table {{
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 12.5pt; color: #3d3528; margin-top: 2mm;
  }}
  .table b {{ color: #6b4a12; font-size: 14pt; }}
  .hint {{
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 6.6pt; color: #9a907d; letter-spacing: 0.2pt;
    text-align: center; line-height: 1.3;
  }}

  /* метка столика и языка на нижней кромке — уходит под рамку */
  .tag {{
    position: absolute; bottom: 1.2mm; left: 0; right: 0;
    text-align: center;
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 4.5pt; color: #b9b1a1; letter-spacing: 0.4pt;
  }}
</style>
</head>
<body>
{body}</body>
</html>"""
    n_cards = sum(1 for c in cards if c)
    return html, n_cards, len(pages), (card_w, card_h)


def main():
    ap = argparse.ArgumentParser(description="PDF с QR-вкладышами на столики под рамку Front.dxf")
    ap.add_argument("--tables", type=int, default=7, help="сколько столиков (по умолчанию 7)")
    ap.add_argument("--langs", default="ru,kk", help="языки карточек: ru, kk (по умолчанию ru,kk)")
    ap.add_argument("--title-ru", default="", help="слово на русской карточке (по умолчанию Menu)")
    ap.add_argument("--title-kk", default="", help="слово на казахской карточке (по умолчанию Мәзір)")
    ap.add_argument("--clearance", type=float, default=0.4,
                    help="насколько вкладыш меньше рамки, мм всего (по умолчанию 0.4)")
    ap.add_argument("--url", default=BASE_URL, help="адрес меню")
    ap.add_argument("-o", "--out", default=str(HERE / "qr-cards.pdf"), help="куда сохранить PDF")
    a = ap.parse_args()

    langs = [s.strip() for s in a.langs.split(",") if s.strip()]
    bad = [l for l in langs if l not in TEXTS]
    if bad:
        sys.exit(f"нет текстов для языка: {', '.join(bad)} (есть: {', '.join(TEXTS)})")
    if len(langs) > ROWS:
        sys.exit(f"на лист влезает языков: {ROWS}")

    tables = list(range(1, a.tables + 1))
    titles = {"ru": a.title_ru, "kk": a.title_kk}
    out = pathlib.Path(a.out).resolve()

    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        html, n_cards, n_pages, (cw, ch) = build_html(
            tables, langs, titles, a.url, a.clearance, workdir)
        page = workdir / "cards.html"
        page.write_text(html, encoding="utf-8")

        subprocess.run(
            [tool("google-chrome", "chromium", "chromium-browser"),
             "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", f"--print-to-pdf={out}", page.as_uri()],
            check=True, capture_output=True,
        )

    print(f"карточек: {n_cards} ({' + '.join(f'{len(tables)} {l}' for l in langs)}), "
          f"листов A4: {n_pages} -> {out}")
    print(f"лист: {cw:.2f} x {ch:.2f} мм, из них видно окно {WIN_W:g} x {WIN_H:g} мм сверху, "
          f"скрытый низ {HIDDEN_B - a.clearance / 2:.2f} мм")
    print(f"зазор между карточками {GAP:g} мм")
    print("печатать в масштабе 100% («фактический размер»), иначе размер поедет")


if __name__ == "__main__":
    main()
