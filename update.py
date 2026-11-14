from logging import (
    FileHandler,
    StreamHandler,
    INFO,
    basicConfig,
    error as log_error,
    info as log_info,
    warning as log_warning,
)
from os import path as ospath, environ, remove
from subprocess import run as srun
from shutil import which as shutil_which
import hashlib
from requests import get as rget
from dotenv import load_dotenv, dotenv_values
from pymongo import MongoClient

if ospath.exists("log.txt"):
    with open("log.txt", "r+") as f:
        f.truncate(0)

if ospath.exists("rlog.txt"):
    remove("rlog.txt")

# Never delete Telegram session files during a deployment or restart.

basicConfig(
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

if ospath.exists("config.env"):
    load_dotenv("config.env", override=False)

try:
    if bool(environ.get("_____REMOVE_THIS_LINE_____")):
        log_error("The README.md file there to be read! Exiting now!")
        exit()
except Exception:
    pass

BOT_TOKEN = environ.get("BOT_TOKEN", "")
if len(BOT_TOKEN) == 0:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

bot_id = BOT_TOKEN.split(":", 1)[0]

DATABASE_URL = environ.get("DATABASE_URL", "")
if len(DATABASE_URL) == 0:
    DATABASE_URL = None

if DATABASE_URL is not None:
    conn = MongoClient(DATABASE_URL)
    db = conn.canonleech
    old_config = db.settings.deployConfig.find_one({"_id": bot_id})
    config_dict = db.settings.config.find_one({"_id": bot_id})
    if config_dict is not None:
        if config_dict.get("UPSTREAM_REPO"):
            environ["UPSTREAM_REPO"] = str(config_dict["UPSTREAM_REPO"])
        if config_dict.get("UPSTREAM_BRANCH"):
            environ["UPSTREAM_BRANCH"] = str(config_dict["UPSTREAM_BRANCH"])
        if config_dict.get("UPDATE_PACKAGES"):
            environ["UPGRADE_PACKAGES"] = str(config_dict.get("UPDATE_PACKAGES"))
    conn.close()


def get_file_hash(filepath):
    if not ospath.exists(filepath):
        return None
    try:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        log_error(f"Failed to calculate hash for {filepath}: {e}")
        return None


def get_uv_path():
    uv_path = shutil_which("uv")
    if not uv_path:
        for path in [
            "/bin/uv",
            "/usr/local/bin/uv",
            "/usr/bin/uv",
            ospath.expanduser("~/.local/bin/uv"),
            ospath.expanduser("~/.cargo/bin/uv"),
        ]:
            if ospath.exists(path):
                uv_path = path
                break
    return uv_path or "uv"


def install_requirements(req_path="requirements.txt", current_hash=None):
    if not ospath.exists(req_path):
        return False
    uv_bin = get_uv_path()
    log_info(f"Installing/updating requirements from {req_path} using {uv_bin}...")
    cmd = f'"{uv_bin}" pip install --system --break-system-packages --no-cache -r "{req_path}"'
    log_info(f"Executing: {cmd}")
    res = srun(cmd, shell=True)
    if res.returncode == 0:
        log_info("Successfully installed requirements with uv pip!")
        saved_hash = current_hash or get_file_hash(req_path)
        if saved_hash:
            try:
                with open(".requirements_installed", "w") as f:
                    f.write(saved_hash)
            except Exception as e:
                log_error(f"Failed to update .requirements_installed: {e}")
        return True
    else:
        log_error(
            f"uv pip install failed with exit code {res.returncode}! Attempting fallback with python3 -m pip..."
        )
        fallback_res = srun(
            f'python3 -m pip install --break-system-packages --no-cache-dir -r "{req_path}"',
            shell=True,
        )
        if fallback_res.returncode == 0:
            log_info("Successfully installed requirements with pip fallback!")
            saved_hash = current_hash or get_file_hash(req_path)
            if saved_hash:
                try:
                    with open(".requirements_installed", "w") as f:
                        f.write(saved_hash)
                except Exception as e:
                    log_error(f"Failed to update .requirements_installed: {e}")
            return True
        else:
            log_error("Failed to install requirements with fallback pip!")
            return False


def check_and_update_requirements(req_hash_before=None):
    req_file = "requirements.txt"
    if not ospath.exists(req_file):
        return

    req_hash_after = get_file_hash(req_file)
    if not req_hash_after:
        return

    installed_hash = None
    if ospath.exists(".requirements_installed"):
        try:
            with open(".requirements_installed", "r") as f:
                installed_hash = f.read().strip()
        except Exception:
            pass

    req_changed = False
    if req_hash_before is not None and req_hash_before != req_hash_after:
        req_changed = True
        log_info("Detected changes in requirements.txt from upstream repository!")
    elif installed_hash is not None and installed_hash != req_hash_after:
        req_changed = True
        log_info("Current requirements.txt differs from installed version!")

    if req_changed:
        install_requirements(req_file, req_hash_after)
    elif not ospath.exists(".requirements_installed"):
        try:
            with open(".requirements_installed", "w") as f:
                f.write(req_hash_after)
        except Exception:
            pass


# Containers are immutable deployments: source updates must happen by rebuilding
# from the selected GitHub repository and commit, not by resetting the live
# container's working tree at startup. This also prevents MongoDB settings from
# silently switching the deployed source to another fork.
UPSTREAM_REPO = environ.get("UPSTREAM_REPO", "").strip()
UPSTREAM_BRANCH = environ.get("UPSTREAM_BRANCH", "main").strip() or "main"

if environ.get("ENABLE_UPSTREAM_UPDATE", "false").strip().lower() == "true":
    log_warning(
        "ENABLE_UPSTREAM_UPDATE is ignored in container deployments. "
        "Pull the intended repository revision and rebuild the image instead."
    )

if environ.get("UPGRADE_PACKAGES", "false").strip().lower() == "true":
    log_warning(
        "UPGRADE_PACKAGES is ignored at runtime. Pin and install dependencies "
        "during the Docker image build to keep deployments reproducible."
    )

check_and_update_requirements(req_hash_before)
