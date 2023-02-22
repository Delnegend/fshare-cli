import json
import os
import requests
import re
import time
from datetime import datetime
from getpass import getpass


APP_KEY = ""
USER_AGENT = ""
FILE_SIZE_LIMIT = 20 * 1024 * 1024  # 20MB
RETRY_ATTEMPTS = 5
RETRY_DELAY = 5


class API:
    MAIN = "https://api.fshare.vn/api"

    LOGIN = MAIN + "/user/login"  # POST
    LOGOUT = MAIN + "/user/logout"  # GET
    GET_INFO = MAIN + "/user/get"  # GET

    UPLOAD = MAIN + "/session/upload"  # POST

    GET_FOLDER_STRUCTURE = MAIN + "/fileops/list"  # GET


class BCOLORS:
    HEADER = '\033[95m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_sign(msg: str, color: str) -> None:
    msglen = len(msg) + 4
    print(color + "╔" + "═" * msglen + "╗")
    print("║  " + msg + "  ║")
    print("╚" + "═" * msglen + "╝" + BCOLORS.ENDC)


def human_readable_size(size_in_byte: str) -> str:
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    for i in range(len(size_name)):
        if size_in_byte < 1024:
            return f"{size_in_byte:.2f} {size_name[i]}"
        size_in_byte /= 1024
    return f"{size_in_byte:.2f} YB"


def get_user_input_option(options: list, default: int = 0) -> tuple:
    """
    @param options: list of options to be printed
    @param default: default option (index of the option in the list)

    Print a list of the given options from 1 to len(options) + 1
    Return (<index of the selected option>, <selected option>)
    """
    for i, option in enumerate(options):
        print(f"{BCOLORS.YELLOW}[{i + 1}]{BCOLORS.ENDC} {option}")
    selected = input("Enter your choice: ")
    while True:
        try:
            if selected == "":
                selected = default + 1
                break
            if int(selected) > len(options):
                selected = input(f"{BCOLORS.RED}Input must be between 1 and {len(options)}: {BCOLORS.ENDC}")
                continue
            selected = int(option)
            break
        except:
            selected = input(f"{BCOLORS.RED}Input must be an integer: {BCOLORS.ENDC}")
    return (selected - 1, options[selected - 1])


class SESSION():
    def __init__(self, user_agent: str, app_key: str):
        self.__token = ""
        self.__session_id = ""
        self.__user_agent = user_agent
        self.__app_key = app_key
        self.__user_info = {}

        if os.path.exists("session.json"):
            try:
                with open("session.json", "r") as f:
                    data = json.load(f)
                    if "token" in data and "session_id" in data:
                        self.__token = data["token"]
                        self.__session_id = data["session_id"]
            except:
                os.remove("session.json")

    # Authentication

    def login(self, username: str, password: str) -> tuple:
        result = requests.post(
            API.LOGIN,
            headers={"User-Agent": self.__user_agent},
            json={"user_email": username, "password": password, "app_key": self.__app_key}
        )
        if result.status_code == 200:
            self.__token = result.json()["token"]
            self.__session_id = result.json()["session_id"]
            with open("session.json", "w") as f:
                json.dump({"token": self.__token, "session_id": self.__session_id}, f)
            return (True, result.json()["msg"])
        else:
            return (False, result.json()["msg"])

    def logout(self) -> tuple:
        result = requests.get(
            API.LOGOUT,
            headers={"Cookie": f"session_id={self.__session_id}"}
        )
        return (True if result.status_code == 200 else False, result.json()["msg"])

    def get_user_info(self) -> bool:

        result = requests.get(
            API.GET_INFO,
            headers={
                "Cookie": f"session_id={self.__session_id}",
                "User-Agent": self.__user_agent
            }
        )

        if result.status_code == 200:
            self.__user_info = result.json()
            return True
        else:
            return False

    # Upload

    # Notes:
    # - Path has "/" at the beginning when it's
    #   - returned from API.GET_FOLDER_STRUCTURE
    #   - requested to self.__get_upload_link
    # - Path doesn't have "/" at the beginning when it's
    #   - requested to API.GET_FOLDER_STRUCTURE
    # - NO TRAILING SLASHES

    def __request_upload_api(self, file_name: str, remote_path: str = "/", file_size: int = 0) -> tuple:
        result = requests.post(
            API.UPLOAD,
            headers={
                "User-Agent": self.__user_agent,
                "Cookie": f"session_id={self.__session_id}"
            },
            json={
                "name": file_name,
                "size": str(file_size),
                "path": remote_path,
                "token": self.__token,
                "secured": 1
            }
        )
        if result.status_code == 200:
            return (True, result.json()["location"])
        else:
            return (False, result.json()["msg"])

    def upload(self, file_path: str, remote_path: str = "/") -> tuple:

        file_name = os.path.basename(file_path)
        file_dir = os.path.dirname(file_path).replace("\\", "/")
        file_size = os.path.getsize(file_path)

        old_file_name = file_name

        # Fshare doesn't allow certain characters in file name
        if re.search(r"[\\/:*?<>!@\"#\$%\^|\-]", file_name):
            file_name = re.sub(r"[\\/:*?<>!@\"#\$%\^|\-]", "_", file_name)
            os.rename(file_path, os.path.join(os.path.dirname(file_path), file_name))
            file_path = os.path.join(os.path.dirname(file_path), file_name)

        remote_path = os.path.join(remote_path, file_dir).replace("\\", "/")
        remote_path = "/" if remote_path == "" else remote_path
        remote_path = "/" + remote_path if remote_path[0] != "/" else remote_path
        remote_path = remote_path[:-1] if remote_path[-1] == "/" else remote_path

        result, message = self.__request_upload_api(file_name, remote_path, file_size)

        if not result:
            return (False, message)
        upload_api = message

        if file_size < 20 * 1024 * 1024:
            with open(file_path, "rb") as f:
                result = requests.put(
                    upload_api,
                    headers={
                        "User-Agent": self.__user_agent,
                        "Cookie": f"session_id={self.__session_id}"
                    },
                    data=f.read()
                )
        else:

            print(f"Uploading {old_file_name} ({human_readable_size(file_size)})...")

            f = open(file_path, "rb")
            chunk_size = 20 * 1024 * 1024
            chunk_count = file_size // chunk_size
            if file_size % chunk_size != 0:
                chunk_count += 1

            start_time = time.time()

            for i in range(chunk_count):
                chunk = f.read(chunk_size)

                for _ in range(RETRY_ATTEMPTS):
                    result = requests.put(
                        upload_api,
                        headers={
                            "User-Agent": self.__user_agent,
                            "Cookie": f"session_id={self.__session_id}",
                            "Content-Range": f"bytes {i * chunk_size}-{i * chunk_size + len(chunk) - 1}/{file_size}"
                        },
                        data=chunk
                    )
                    if result.status_code == 200:
                        break
                    time.sleep(RETRY_DELAY)

                progress = {
                    "percentage": round((i + 1) / chunk_count * 100, 2),
                    "bar": "[{}{}]".format(
                        "=" * int((i + 1) / chunk_count * 20),
                        " " * (20 - int((i + 1) / chunk_count * 20))
                    ),
                    "elapsed_time": time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time)),
                    "eta_time": time.strftime("%H:%M:%S", time.gmtime((time.time() - start_time) / (i + 1) * (chunk_count - i - 1))),
                    "speed": round((i + 1) * chunk_size / (time.time() - start_time) / 1024 / 1024, 2)
                }

                print(" {}% {} Elapsed: {} | ETA: {} | {} MB/s {}".format(
                    progress["percentage"],
                    progress["bar"],
                    progress["elapsed_time"],
                    progress["eta_time"],
                    progress["speed"],
                    " " * 20
                ), end="\r")
            f.close()
            print()

        # Rename file back to original name
        if file_name != old_file_name:
            os.rename(file_path, os.path.join(os.path.dirname(file_path), old_file_name))

        if result.status_code == 200:
            res = result.json()
            return (
                True,
                "{}Uploaded{} {}{}{} {}to{} {}{}{}".format(
                    BCOLORS.GREEN,
                    BCOLORS.ENDC,
                    BCOLORS.BLUE,
                    res["name"],
                    BCOLORS.ENDC,
                    BCOLORS.GREEN,
                    BCOLORS.ENDC,
                    BCOLORS.BLUE,
                    res["url"],
                    BCOLORS.ENDC
                )
            )
        else:
            return (False, result.json()["error"])

    def __str__(self):
        if self.__user_info:

            vip_duration_left = ""
            vip_expire_time = datetime.fromtimestamp(int(self.__user_info["expire_vip"]))
            vip_days_left = (vip_expire_time - datetime.now()).days
            if vip_days_left > 0:
                vip_duration_left += f"{vip_days_left} days "
            vip_hours_left = (vip_expire_time - datetime.now()).seconds // 3600
            if vip_hours_left > 0:
                vip_duration_left += f"{vip_hours_left} hours "
            vip_minutes_left = (vip_expire_time - datetime.now()).seconds // 60 % 60
            if vip_minutes_left > 0:
                vip_duration_left += f"{vip_minutes_left} minutes "

            return f"Fshare CLI - {self.__user_info['email']} - {vip_duration_left}left"

        else:
            return "Fshare CLI"

    # Navigation

    def __request_folder_structure(self, remote_path: str = "") -> tuple:
        pages_data = []
        page_count = 0
        while True:
            result = requests.get(
                API.GET_FOLDER_STRUCTURE,
                headers={
                    "User-Agent": self.__user_agent,
                    "Cookie": f"session_id={self.__session_id}"
                },
                params={
                    "pageIndex": page_count,
                    "dirOnly": 1,
                    "path": remote_path
                }
            )
            if result.status_code == 200:
                result = result.json()
                pages_data += result
                page_count += 1
                if result == []:
                    break
            else:
                return (False, result.json())
        return (True, pages_data)

    def select_remote_dir(self) -> tuple:

        final_remote_dir = ""
        last_message = ""

        while True:
            print("\033c", end="")
            print(last_message) if last_message else None
            last_message = ""

            print_sign("Where to upload?", BCOLORS.GREEN)
            print(f"Current path: {BCOLORS.BLUE}{final_remote_dir if final_remote_dir != '' else '<ROOT>'}{BCOLORS.ENDC}")

            print("-" * 20)
            success, result = self.__request_folder_structure(final_remote_dir)
            if not success:
                return (False,result)
            remote_folders = result

            folders = [folder["name"] for folder in remote_folders]
            for i, folder in enumerate(folders):
                print(f"{BCOLORS.YELLOW}[{i + 1}]{BCOLORS.ENDC} {folder}")
            if len(folders) == 0:
                print(f"{BCOLORS.RED}No folder found in this path!{BCOLORS.ENDC}")

            print("-" * 20)
            print(f"{BCOLORS.YELLOW}[0]{BCOLORS.ENDC} Go back")
            print(f"{BCOLORS.YELLOW}[x]{BCOLORS.ENDC} Select this folder")

            print("Your choice: ", end="")

            choice = input()
            if choice.lower() == "x":
                break
            elif choice == "0":
                if final_remote_dir == "":
                    last_message = BCOLORS.RED + "You're already at the root folder!" + BCOLORS.ENDC
                else:
                    final_remote_dir = "/".join(final_remote_dir.split("/")[:-1])
            elif choice in [str(i) for i in range(1, len(remote_folders) + 1)]:
                final_remote_dir = os.path.join(final_remote_dir, remote_folders[int(choice) - 1]["name"]).replace("\\", "/")
            else:
                last_message = f"{BCOLORS.RED}Invalid choice, try again!{BCOLORS.ENDC}"
        return (True, final_remote_dir)


def main() -> int:
    last_message = ""  # For printing messages before the main loop of the program

    session = SESSION(app_key=APP_KEY, user_agent=USER_AGENT)

    # Check token, session_id and login if needed
    while True:
        if not session.get_user_info():
            print(f"{BCOLORS.RED}You're not logged in yet!{BCOLORS.ENDC}")

            email = input("Email: ")
            while not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                print(f"{BCOLORS.RED}Invalid email, try again: {BCOLORS.ENDC}", end="")
                email = input()
            password = input("Password: ")

            result, message = session.login(email, password)
            if result:
                last_message = f"{BCOLORS.GREEN}Logged in successfully!{BCOLORS.ENDC}"
            else:
                last_message = f"{BCOLORS.RED}Error: {message}{BCOLORS.ENDC}"
        else:
            break

    while True:

        print("\033c", end="")

        print(last_message) if last_message else None
        print_sign(str(session), BCOLORS.GREEN)
        print(f"{BCOLORS.YELLOW}[1]{BCOLORS.ENDC} Upload file")
        print(f"{BCOLORS.YELLOW}[2]{BCOLORS.ENDC} Upload folders")
        print(f"-"*20)
        print(f"{BCOLORS.YELLOW}[3]{BCOLORS.ENDC} Logout")
        print(f"{BCOLORS.YELLOW}[4]{BCOLORS.ENDC} Exit")

        choice = input("Your choice: ")

        while True:
            try:
                if int(choice) not in range(1, 6):
                    raise ValueError
                choice = int(choice)
                break
            except ValueError:
                pass
            print("Invalid choice, please try again: ", end="")
            choice = input()

        match choice:
            case 1:  # Upload file
                print("\nChoose a file to upload: ")
                all_files = [f for f in os.listdir(".") if os.path.isfile(f)]
                for i, f in enumerate(all_files):
                    file_size = os.path.getsize(f)
                    print(
                        "{}[{}]{} {} ({}{}{})".format(
                            BCOLORS.YELLOW,
                            i + 1,
                            BCOLORS.ENDC,
                            f,
                            BCOLORS.BLUE,
                            human_readable_size(file_size),
                            BCOLORS.ENDC
                        )
                    )
                choice = input("Your choice: ")
                while True:
                    try:
                        if int(choice) in range(1, len(all_files) + 1):
                            break
                    except:
                        pass
                    print("Invalid choice, please try again: ", end="")
                    choice = input()
                file_path = all_files[int(choice) - 1]

                # remote_path = session.select_remote_dir()
                success, remote_path = session.select_remote_dir()
                if not success:
                    print(BCOLORS.RED + remote_path + BCOLORS.ENDC)
                    continue

                success, content = session.upload(file_path, remote_path)
                if not success:
                    print(BCOLORS.RED + message + BCOLORS.ENDC)
                    continue
                last_message = content

            case 2:  # Upload folders
                print("\nChoose a folder to upload: ")
                all_folders = [f for f in os.listdir(".") if os.path.isdir(f)]
                _, folder_path = get_user_input_option(all_folders)

                remote_path = session.select_remote_dir()

                all_files = []
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        all_files.append(os.path.join(root, file))

                for file in all_files:
                    result, message = session.upload(file, remote_path)
                    if result:
                        print(BCOLORS.GREEN + message + BCOLORS.ENDC)
                    else:
                        print(BCOLORS.RED + message + BCOLORS.ENDC)
                        break

            case 3:  # Logout
                result = session.logout()
                if result[0]:
                    last_message = BCOLORS.GREEN + result[1] + BCOLORS.ENDC
                else:
                    last_message = BCOLORS.RED + result[1] + BCOLORS.ENDC
                raise KeyboardInterrupt

            case 4:
                return 0

        input("Press any key to continue...")


if __name__ == '__main__':
    try:
        if main() == 0:
            print(f"{BCOLORS.GREEN}Exiting...{BCOLORS.ENDC}")
    except KeyboardInterrupt:
        print(f"\n{BCOLORS.RED}Exiting...{BCOLORS.ENDC}")
