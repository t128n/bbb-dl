import os
import shutil
import subprocess
import sys
from io import StringIO
from yarl import URL

from bbb_dl.version import __version__
from bbb_dl.utils import BBBDLCookieJar, convert_to_aiohttp_cookie_jar


def test_version():
    assert isinstance(__version__, str)
    assert len(__version__.split(".")) >= 2


def test_main_cli_help():
    bbb_dl_bin = shutil.which("bbb-dl")
    if bbb_dl_bin:
        cmd = [bbb_dl_bin, "--help"]
    else:
        cmd = [sys.executable, "-c", "import bbb_dl.main; bbb_dl.main.main()", "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "Big Blue Button Downloader" in res.stdout
    assert "bbb-dl auth" in res.stdout


def test_batch_cli_help():
    bbb_batch_bin = shutil.which("bbb-dl-batch")
    if bbb_batch_bin:
        cmd = [bbb_batch_bin, "--help"]
    else:
        cmd = [sys.executable, "-c", "import bbb_dl.batch; bbb_dl.batch.main()", "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "usage:" in res.stdout


def test_auth_cli_help():
    bbb_dl_bin = shutil.which("bbb-dl")
    if bbb_dl_bin:
        cmd = [bbb_dl_bin, "auth", "--help"]
    else:
        cmd = [sys.executable, "-c", "import bbb_dl.main; bbb_dl.main.main()", "auth", "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "login" in res.stdout
    assert "set-cookie" in res.stdout
    assert "list" in res.stdout
    assert "clear" in res.stdout


def test_auth_cookie_operations(tmp_path):
    working_dir = str(tmp_path)
    bbb_dl_bin = shutil.which("bbb-dl")
    base_cmd = [bbb_dl_bin] if bbb_dl_bin else [sys.executable, "-c", "import bbb_dl.main; bbb_dl.main.main()"]

    # 1. Set cookie
    set_cmd = base_cmd + ["auth", "-wd", working_dir, "set-cookie", "example.com", "test_cookie", "secret_val_123"]
    res = subprocess.run(set_cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    cookies_file = os.path.join(working_dir, "cookies.txt")
    assert os.path.isfile(cookies_file)

    # 2. List cookies
    list_cmd = base_cmd + ["auth", "-wd", working_dir, "list"]
    res = subprocess.run(list_cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "example.com" in res.stdout
    assert "test_cookie" in res.stdout

    # 3. Clear cookies
    clear_cmd = base_cmd + ["auth", "-wd", working_dir, "clear"]
    res = subprocess.run(clear_cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert not os.path.isfile(cookies_file)


def test_cookie_jar_conversion():
    cookie_text = (
        "# Netscape HTTP Cookie File\n"
        "example.com\tFALSE\t/\tTRUE\t1893456000\tmy_auth_token\txyz123\n"
    )
    jar = BBBDLCookieJar(StringIO(cookie_text))
    jar.load(ignore_discard=True, ignore_expires=True)
    aio_jar = convert_to_aiohttp_cookie_jar(jar)

    filtered = aio_jar.filter_cookies(URL("https://example.com/presentation/test/metadata.xml"))
    assert "my_auth_token" in filtered
    assert filtered["my_auth_token"].value == "xyz123"
