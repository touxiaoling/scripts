# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx[http2]",
#     "pillow",
#     "tqdm",
# ]
#
# [[tool.uv.index]]
# url = "https://pypi.tuna.tsinghua.edu.cn/simple"
# default = true
# ///
import sys
from io import BytesIO
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

import httpx
from PIL import Image
from tqdm.auto import tqdm

import utils


cfg = utils.load_config()
db = utils.load_kvdb()
_logger = logging.getLogger(__name__)

s = httpx.AsyncClient(http2=True, follow_redirects=True, verify=False, timeout=10)
s.headers.update(cfg["headers"])
# s.cookies.update(cfg.session.cookies)


@utils.retry(retry_time=cfg["max_retries"], delay=1)
@utils.limit_async(5)
async def safe_urlopen(url):
    response = await s.get(url, timeout=10)
    response.raise_for_status()
    return response


async def download_img(zoom_level, dt, col, row):
    dt = dt.strftime("%Y/%m/%d/%H%M%S")
    response = None
    url: str = cfg["host_asia"] + cfg["template"].format(zoom_level, dt, col, row)
    try:
        response = await safe_urlopen(url)
        response = BytesIO(response.content)
    except Exception as e:
        _logger.error(f"Error downloading image from {url}: {e}")

    return col, row, response


async def get_fragments(dt: datetime, zoom_level):
    tasks = []
    format_dt = dt.strftime("%d_%H%M")

    for col in range(zoom_level):
        for row in range(zoom_level):
            if not db.get(f"{zoom_level}_{format_dt}_{col}_{row}", False):
                tasks.append(download_img(zoom_level, dt, col, row))

    completed_num = 0
    total_num = len(tasks)
    _logger.debug(f"Total fragments to download: {total_num}")
    if total_num <= 0:
        db[f"{zoom_level}_{format_dt}"] = True
        return

    if not cfg["tqdm"]:
        tqdm = lambda *args, **kwargs: args[0]

    for task in tqdm(asyncio.as_completed(tasks), total=total_num, desc=f"Downloading {zoom_level}_{format_dt}"):
        col, row, img_bytes = await task
        if img_bytes:
            db[f"{zoom_level}_{format_dt}_{col}_{row}"] = True
            completed_num += 1

            if completed_num == total_num:
                db[f"{zoom_level}_{format_dt}"] = True

            yield col, row, img_bytes


async def get_coastline(zoom_level, save_path: Path, tg: asyncio.TaskGroup):
    png_unit_size = cfg["png_unit_size"]
    png_width = png_unit_size * zoom_level
    png_height = png_width
    file_path = save_path / f"coastline_{zoom_level:02d}.webp"


async def turncated_img(zoom_level, format_dt, file_path: Path):
    _logger.debug(f"Truncated image detected for {zoom_level}_{format_dt}. Reinitializing fragments.")
    file_path.unlink(missing_ok=True)

    for col in range(zoom_level):
        for row in range(zoom_level):
            db[f"{zoom_level}_{format_dt}_{col}_{row}"] = False
    db[f"{zoom_level}_{format_dt}"] = False


@utils.limit_async(2)
async def stitching(dt: datetime, zoom_level, save_path: Path, tg: asyncio.TaskGroup):
    png_unit_size = cfg["png_unit_size"]
    png_width = png_unit_size * zoom_level
    png_height = png_width
    dir_dt = dt.strftime("%Y%m")

    save_dir = save_path / f"{zoom_level:02d}_{dir_dt}"
    save_dir.mkdir(exist_ok=True)

    format_dt = dt.strftime("%d_%H%M")
    file_path = save_dir / f"{format_dt}.webp"

    if not file_path.exists():
        _logger.debug(f"checking image not exists {file_path}...")
        await turncated_img(zoom_level, format_dt, file_path)

    if db.get(f"{zoom_level}_{format_dt}", False):
        return

    if not file_path.exists():
        _logger.debug(f"Creating new image {zoom_level}_{format_dt}...")
        target = await asyncio.to_thread(Image.new, "RGB", (png_width, png_height), "black")
    else:
        try:
            target = await asyncio.to_thread(Image.open, file_path)
        except Exception as e:
            _logger.error(f"Error opening existing image: {e}")
            await turncated_img(zoom_level, format_dt, file_path)

    _logger.info(f"Stitching image {zoom_level}_{format_dt}...")
    async for col, row, img_bytes in get_fragments(dt, zoom_level):
        with Image.open(img_bytes) as img:
            await asyncio.to_thread(target.paste, img, (col * png_unit_size, row * png_unit_size))

    async def tail_process():
        try:
            _logger.info(f"Saving stitched image {file_path}...")
            await asyncio.to_thread(target.save, file_path, "WEBP", lossless=True, optimize=True, quality=90, method=6)
            target.close()
            _logger.info(f"Image saved successfully: {file_path}")
        except Exception as e:
            _logger.error(f"Error saving image {file_path}: {e}")
            await turncated_img(zoom_level, format_dt, file_path)

    tg.create_task(tail_process())


async def get_latest_fragments_info():
    res = await safe_urlopen(cfg["host"] + cfg["json"])

    json_data = res.json()
    _logger.info(f"Received date: {json_data}")
    date_str: str = json_data.get("date", "")
    if not date_str:
        raise ValueError("Received invalid date string in response.")

    date_format = "%Y-%m-%d %H:%M:%S"
    dt = datetime.strptime(date_str, date_format)

    return dt


async def main():
    zoom_level = cfg["zoom_level"]
    save_path = Path(cfg["save_path"])

    save_path.mkdir(exist_ok=True)

    latest_dt = await get_latest_fragments_info()
    dt = latest_dt - timedelta(hours=24)
    async with asyncio.TaskGroup() as tg:
        while dt <= latest_dt:
            tg.create_task(stitching(dt, zoom_level, save_path, tg))
            dt += timedelta(minutes=10)

    _logger.info("Processing completed successfully.")


if __name__ == "__main__":
    FORMAT = "%(asctime)s %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO, stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARN)

    asyncio.run(main())

# */10 * * * *
