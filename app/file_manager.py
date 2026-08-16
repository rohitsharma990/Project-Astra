from pathlib import Path
from . import ui


def create_folder(folder_name=None):
    try:
        if folder_name is None:
            folder_name = input("Folder Name : ")

        folder = Path("Files")
        folder.mkdir(exist_ok=True)

        path = folder / folder_name

        if not path.exists():
            path.mkdir()
            ui.success("Folder Created Successfully")
        else:
            ui.warning("Folder already exists.")

    except Exception as err:
        ui.error(f"Something went wrong: {err}")


def create_file(file_name=None):
    try:
        if file_name is None:
            file_name = input("File Name : ")

        folder = Path("Files")
        folder.mkdir(exist_ok=True)

        path = folder / file_name

        if not path.exists():

            with open(path, "w") as fs:
                data = input("Write Something : ")
                fs.write(data)

            ui.success("File Created Successfully")

        else:
            ui.warning("File already exists.")

    except Exception as err:
        ui.error(f"Something went wrong: {err}")
