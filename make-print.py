#!/usr/bin/env python3
"""Собирает все вкладыши в один PDF, укладывая их на листы A4 плотно.

Вёрстку карточек не дублирует: каждую рисует её собственный генератор
(make-cards.py, make-profile.py, make-tips.py) как отдельный документ, а
сюда он попадает фреймом. Поэтому правки в генераторах доходят в общий
файл сами, без синхронизации руками.

Откуда экономия против простой склейки трёх PDF:
  * треугольники кладутся через один вверх ногами и входят по 6 на лист
    вместо 4 — контуры дополняют друг друга, шаг получается 47.02 мм
    вместо 73.43;
  * ряды разных видов делят общий лист, поэтому хвосты по 1-2 карточки
    не занимают отдельных страниц.

    ./make-print.py
    ./make-print.py --tables 7 --sides 7

Нужен google-chrome (или chromium).
"""
import argparse, html, importlib.util, math, pathlib, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
A4_W, A4_H = 210.0, 297.0
MARGIN = 9.0        # минимальное поле листа, мм — меньше принтер не пропечатает
ROW_GAP = 5.0       # просвет между рядами
COL_GAP = 5.0       # просвет между прямоугольными карточками
TRI_GAP = 2.2       # горизонтальный просвет между наклонными кромками


def load(name):
    """Генератор рядом — как модуль (в имени дефис, обычный import не возьмёт)."""
    path = HERE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def one_card(mod, make):
    """Документ с одной карточкой: временно схлопываем сетку генератора в 1x1."""
    cols, rows = mod.COLS, mod.ROWS
    mod.COLS, mod.ROWS = 1, 1
    try:
        doc = make()
    finally:
        mod.COLS, mod.ROWS = cols, rows
    # во фрейме полоски прокрутки печатаются как есть — глушим; а фон обязан
    # быть прозрачным: соседние треугольники заходят друг другу в габарит, и
    # белая подложка фрейма затёрла бы контур соседа
    return doc.replace(
        "</style>",
        "  html, body { overflow: hidden; background: transparent !important; }\n</style>",
        1)


def main():
    ap = argparse.ArgumentParser(description="Общий PDF со всеми вкладышами")
    ap.add_argument("--tables", type=int, default=7, help="столиков (карточек меню вдвое)")
    ap.add_argument("--sides", type=int, default=7, help="подставок (боковин каждого вида)")
    ap.add_argument("-o", "--out", default=str(HERE / "print-all.pdf"))
    a = ap.parse_args()

    cards = load("make-cards")
    prof = load("make-profile")
    tips = load("make-tips")

    card_w = cards.FRONT_W - 0.4
    card_h = cards.SHEET_H - 0.4
    tri_w, tri_h = prof.SHEET_W, prof.SHEET_H
    # шаг между соседними треугольниками, когда каждый второй перевёрнут.
    # контуры дополняют друг друга, и предельное расстояние выходит одним и тем
    # же на всех высотах: правый край макушки плюс вынос ската за высоту нижней
    # планки. Отсюда 47.02 мм вместо 73.43 — три штуки в ряд вместо двух.
    flat_w = prof.SHEET[3][0] - prof.SHEET[2][0]          # плоская макушка контура
    rect_h = tri_h - prof.SHEET[1][1]                     # нижняя планка во всю ширину
    step = (tri_w + flat_w) / 2 + math.tan(prof.SLOPE) * rect_h + TRI_GAP

    tmp = tempfile.TemporaryDirectory()
    work = pathlib.Path(tmp.name)

    def menu_doc(table, lang):
        return one_card(cards, lambda: cards.build_html(
            [table], [lang], {"ru": "", "kk": ""}, cards.BASE_URL, 0.4, work)[0])

    prof_img = (HERE / "img/profile-art.jpg").as_uri()
    def prof_doc(n):
        return one_card(prof, lambda: prof.build_html(1, ["kk"], 0.4, prof_img, 83.0)[0])

    tips_img = (HERE / "img/tips-art.jpg").as_uri()
    tips_qr = (HERE / "img/tips-qr.png").as_uri()
    L = tips.layout()
    def tips_doc(n):
        return one_card(tips, lambda: tips.build_html(1, tips_img, tips_qr, L)[0])

    # ---- ряды: меню парами «рус над каз», боковины по три ----
    rows = []
    tbl = list(range(1, a.tables + 1))
    for i in range(0, len(tbl), 3):
        chunk = tbl[i:i+3]
        if len(chunk) == 3:
            for lang in ("ru", "kk"):
                rows.append(("menu", [menu_doc(n, lang) for n in chunk],
                             f"меню {lang} — столики {chunk[0]}-{chunk[-1]}"))
        else:   # хвост: русские и казахские в одном ряду, чтобы не плодить ряды
            rows.append(("menu",
                         [menu_doc(n, l) for n in chunk for l in ("ru", "kk")],
                         f"меню рус+каз — столик {chunk[0]}"))

    tri_pool = [("пейзаж", prof_doc(n)) for n in range(1, a.sides + 1)]
    tri_pool += [("на чай", tips_doc(n)) for n in range(1, a.sides + 1)]
    tail = []
    for kind in ("пейзаж", "на чай"):
        same = [d for k, d in tri_pool if k == kind]
        for i in range(0, len(same), 3):
            chunk = same[i:i+3]
            if len(chunk) == 3:
                rows.append(("tri", chunk, f"боковины «{kind}» x3"))
            else:
                tail += chunk
    for i in range(0, len(tail), 3):
        rows.append(("tri", tail[i:i+3], f"боковины вперемешку x{len(tail[i:i+3])}"))

    # ---- раскладка рядов по листам ----
    H = {"menu": card_h, "tri": tri_h}
    pages, cur, cur_h = [], [], 0.0
    for row in rows:
        h = H[row[0]]
        need = h if not cur else cur_h + ROW_GAP + h
        if need > A4_H - 2 * MARGIN and cur:
            pages.append((cur, cur_h)); cur, cur_h = [row], h
        else:
            cur, cur_h = cur + [row], need
    if cur:
        pages.append((cur, cur_h))

    body, listing = "", []
    for pi, (page, total) in enumerate(pages, 1):
        y = (A4_H - total) / 2
        slots = ""
        for kind, docs, label in page:
            n = len(docs)
            if kind == "menu":
                w = n * card_w + (n - 1) * COL_GAP
                x = (A4_W - w) / 2
                for i, d in enumerate(docs):
                    slots += slot(x + i * (card_w + COL_GAP), y, card_w, card_h, False, d)
                y += card_h + ROW_GAP
            else:
                w = (n - 1) * step + tri_w
                x = (A4_W - w) / 2
                for i, d in enumerate(docs):
                    slots += slot(x + i * step, y, tri_w, tri_h, i % 2 == 1, d)
                y += tri_h + ROW_GAP
        body += f'<div class="sheet">{slots}</div>\n'
        listing.append(f"  лист {pi}: " + "; ".join(r[2] for r in page))

    doc = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Все вкладыши</title>
<style>
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #fff; }}
  .sheet {{
    position: relative; width: {A4_W}mm; height: {A4_H}mm;
    overflow: hidden; page-break-after: always;
  }}
  .sheet:last-child {{ page-break-after: auto; }}
  .slot {{ position: absolute; overflow: hidden; }}
  .slot iframe {{
    width: 100%; height: 100%; border: 0; display: block; background: transparent;
  }}
  .slot.flip iframe {{ transform: rotate(180deg); }}
</style>
</head>
<body>
{body}</body>
</html>"""

    out = pathlib.Path(a.out).resolve()
    page_file = work / "print-all.html"
    page_file.write_text(doc, encoding="utf-8")
    chrome = shutil.which("google-chrome") or shutil.which("chromium") \
        or shutil.which("chromium-browser")
    if not chrome:
        sys.exit("не найден google-chrome / chromium")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                    "--no-pdf-header-footer", f"--print-to-pdf={out}", page_file.as_uri()],
                   check=True, capture_output=True)
    tmp.cleanup()

    print(f"{out} — листов A4: {len(pages)}")
    print("\n".join(listing))
    print(f"шаг треугольников в ряду {step:.2f} мм при ширине листа {tri_w:.2f} — "
           "каждый второй перевёрнут")
    print("печатать в масштабе 100% («фактический размер»), поля «нет»")


def slot(x, y, w, h, flip, doc):
    cls = "slot flip" if flip else "slot"
    src = html.escape(doc, quote=True)
    return (f'<div class="{cls}" style="left:{x:.3f}mm;top:{y:.3f}mm;'
            f'width:{w:.3f}mm;height:{h:.3f}mm"><iframe srcdoc="{src}"></iframe></div>')


if __name__ == "__main__":
    main()
