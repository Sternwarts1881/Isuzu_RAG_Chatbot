import os
import glob


def find_file_paths(data_path, file_extention_to_find):

    try:
        if not os.path.exists(data_path):
            raise FileNotFoundError(" data path not found ")

        folders = os.listdir(data_path)

        if not folders:
            raise FileNotFoundError(" no folders not found ")

        target_file_dir_list = []
        for folder in folders:

            car_dir = os.path.join(data_path, folder)
            if not car_dir:
                raise FileNotFoundError(
                    f"Car directory not found: {car_dir} doesn't exist"
                )

            file_type = "*." + file_extention_to_find
            search_pattern = os.path.join(car_dir, "**", file_type)
            target_files = glob.glob(search_pattern, recursive=True)

            for files in target_files:
                target_file_dir_list.append(files)
            if not target_file_dir_list:
                raise FileNotFoundError(f"No {file_extention_to_find} files were found")

        print(f"find_file_paths(): success, sample location: {target_file_dir_list[0]}")
        return target_file_dir_list

    except Exception as error:
        raise FileNotFoundError(error)
