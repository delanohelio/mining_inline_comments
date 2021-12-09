import argparse

from lib.utils import file_json_utils as json_util
from lib.utils import multiprocess
from lib.github import FetchPRsData, FilterPRs, PRsDataManager
from lib.samples import GenerateCSV
from lib.changes import ExtractCodeChange

from datetime import datetime
import os
import glob
import subprocess


def fetch_info_reviews_repositories(seart_input_path_file, output_path, num_threads=1):
    print("Fetching info of pull requests in repositories"
          "If the file was downloaded it will be skipped")
    print(f"SEART input file path: {seart_input_path_file}")
    print(f"Output: {output_path}")

    list_repositories = json_util.open_json(seart_input_path_file)["items"]

    list_arguments_repositories = []
    for repository in list_repositories:
        arguments_repository = {"repository_name": repository["name"],
                                "repository_createat": repository["createdAt"],
                                "output_path": output, "overwrite": False}
        list_arguments_repositories.append(arguments_repository)

    return multiprocess.multiprocessing_function(FetchPRsData.get_info_prs_of_repository, list_arguments_repositories,
                                                 num_threads)


def filter_prs(list_repositories, input_path, output, threads=1, overwrite=False, start_date_str=None,
               end_date_str=None,
               merged_str=None):
    print("Filtering pull requests in 2020 that have at least one inline comment")
    print(f"Input path: {input_path}")
    print(f"Output: {output}")
    print(f"Threads: {threads}")
    print(f"Start date: {start_date_str}")
    print(f"End date: {end_date_str}")
    start_date = datetime.fromisoformat(start_date_str)
    end_date = datetime.fromisoformat(end_date_str)
    merged = None
    if merged_str is not None and merged_str.lower() == "true":
        merged = True
    elif merged_str is not None and merged_str.lower() == "false":
        merged = False
    print(f"Merged: {merged}")

    list_arguments_repositories = []
    for repository_name in list_repositories:
        # To filter by merged, True means just merged prs, False means just not merged prs,
        # and None means not use this filter.
        arguments_repository = {"repository_name": repository_name,
                                "input_path": input_path,
                                "output_path": output,
                                "num_min_inline": 1,
                                "filter_by_merged_status": merged,
                                "filter_by_created_start": start_date,
                                "filter_by_created_end": end_date,
                                "overwrite": overwrite}
        list_arguments_repositories.append(arguments_repository)

    multiprocess.multiprocessing_function(FilterPRs.select_prs_by_date_and_num_of_inline_reviews_by_repository,
                                          list_arguments_repositories, threads)


def fetch_pr_details_repositories(list_repositories, prs_input_file, path_output, num_threads=1):
    print(f"Fetching details of pull requests in the file {prs_input_file}"
          "If the file was downloaded it will be skipped")
    print(f"Output path: {path_output}")
    print(f"Threads: {num_threads}")

    list_arguments_pull_requests = []
    for repository_name in list_repositories:
        repository_input_file = f"{prs_input_file}/{repository_name.replace('/', '_')}.json"
        pull_requests_info = json_util.open_json(repository_input_file)

        for pull_request in pull_requests_info:
            owner, name = pull_request["repository"].split("/")
            number = pull_request["number"]
            pr_file_path = f"{path_output}/{owner}_{name}/pr_{number}.json"
            arguments_repository = {"owner": owner, "name": name, "pr_number": number,
                                    "save_file_path": pr_file_path, "overwrite": False}
            list_arguments_pull_requests.append(arguments_repository)

    return multiprocess.multiprocessing_function(FetchPRsData.fetch_pull_request_details, list_arguments_pull_requests,
                                                 num_threads)


def fetch_pr_review_threads_repositories(list_repositories, prs_input_file, path_output, num_threads=1):
    print(f"Fetching reviews threads of pull requests in the file {prs_input_file}"
          "If the file was downloaded it will be skipped")
    print(f"Output path: {path_output}")
    print(f"Threads: {num_threads}")

    list_arguments_pull_requests = []
    for repository_name in list_repositories:
        repository_input_file = f"{prs_input_file}/{repository_name.replace('/', '_')}.json"
        pull_requests_info = json_util.open_json(repository_input_file)

        for pull_request in pull_requests_info:
            owner, name = pull_request["repository"].split("/")
            number = pull_request["number"]
            pr_file_path = f"{path_output}/{owner}_{name}/review_thread_pr_{number}.json"
            arguments_repository = {"owner": owner, "name": name, "pr_number": number,
                                    "save_file_path": pr_file_path, "overwrite": False}
            list_arguments_pull_requests.append(arguments_repository)

    return multiprocess.multiprocessing_function(FetchPRsData.fetch_pull_request_review_threads,
                                                 list_arguments_pull_requests,
                                                 num_threads)


def remove_prs_files_not_in_prs_filtered(repository_prs_filtered_list, repository_prs_detail_files_list):
    repository_prs_filtered_processed_list = list(map(lambda pr: f"pr_{pr['number']}", repository_prs_filtered_list))
    pr_files_to_remove = filter(
        lambda pr_file: pr_file.split("/")[-1][:-5] not in repository_prs_filtered_processed_list,
        repository_prs_detail_files_list)

    for file in pr_files_to_remove:
        os.remove(file)


def clean_file_prs_details(list_repositories, prs_filtered_path, prs_details_path, threads=1):
    list_arguments_remove_prs_files = []
    for repository_name in list_repositories:
        repository_dir_name = repository_name.replace('/', '_')
        repo_filtered_prs = json_util.open_json(f"{prs_filtered_path}/{repository_dir_name}.json")
        repo_details_prs = glob.glob(f"{prs_details_path}/{repository_dir_name}/pr_*.json")
        arguments_repository = {"repository_prs_filtered_list": repo_filtered_prs,
                                "repository_prs_detail_files_list": repo_details_prs}
        list_arguments_remove_prs_files.append(arguments_repository)

    multiprocess.multiprocessing_function(remove_prs_files_not_in_prs_filtered, list_arguments_remove_prs_files,
                                          threads)


def clean_file_prs_details_with_errors(list_repositories, prs_input_file):
    print(f"Removing files with errors of path {prs_input_file}")

    for repository_name in list_repositories:
        repository_dir_name = repository_name.replace('/', '_')
        repository_prs_details_path = f"{prs_input_file}/{repository_dir_name}"
        repository_prs_details_files = glob.glob(f"{repository_prs_details_path}/*.json")
        for pr_file_name in repository_prs_details_files:
            pr_file = json_util.open_json(pr_file_name)
            if "errors" in pr_file:
                os.remove(pr_file_name)
                print(f"file {pr_file_name} removed.")


def process_prs_data(list_repositories, prs_input_file, path_output, num_threads=1):
    list_arguments_process_prs = []
    for repository_name in list_repositories:
        repository_dir_name = repository_name.replace('/', '_')
        repository_prs_details_files = glob.glob(f"{prs_input_file}/{repository_dir_name}/pr_*.json")
        repository_prs_review_thread_path = f"{prs_input_file}/{repository_dir_name}"

        for pr_file_path in repository_prs_details_files:
            pr_file_name = pr_file_path.split("/")[-1]
            arguments_process_pr = {"pr_detail_file_path": pr_file_path,
                                    "pr_review_details_file_path": f"{repository_prs_review_thread_path}/review_thread_{pr_file_name}",
                                    "output_file_path": f"{path_output}/{repository_dir_name}/{pr_file_name}"}
            list_arguments_process_prs.append(arguments_process_pr)

    multiprocess.multiprocessing_function(PRsDataManager.process_prs_data_by_pr, list_arguments_process_prs,
                                          num_threads)


def evaluate_acceptable_timeline_item(timeline_item):
    if timeline_item["type"] == "commit":
        return True
    if timeline_item["type"] == "forcePushed":
        if timeline_item["oid"] is not None:
            return True
    if timeline_item["type"] == "inlineReview":
        if timeline_item["path"][-4:] == "java" and timeline_item["originalCommit"] is not None:
            return True
    return False


def evaluate_acceptable_pull_request(pull_request):
    return any(item["type"] == "inlineReview" for item in pull_request["timeline"])


def filter_inline_comments_and_prs(list_repositories, prs_input_file, path_output, num_threads=1):
    print(f"Filtering inline reviews of pull request in {prs_input_file}")
    print(f"Output in {path_output}")
    print(f"Threads {num_threads}")
    list_arguments_filter_inline = []
    for repository_name in list_repositories:
        repository_dir_name = repository_name.replace('/', '_')
        repository_processed_prs_files = glob.glob(f"{prs_input_file}/{repository_dir_name}/*.json")

        for pr_file_path in repository_processed_prs_files:
            pr_file_name = pr_file_path.split("/")[-1]
            arguments_filter_inline = {"processed_pr_file_path": pr_file_path,
                                       "validate_timeline_item_function": evaluate_acceptable_timeline_item,
                                       "validate_pr_function": evaluate_acceptable_pull_request,
                                       "output_file_path": f"{path_output}/{repository_dir_name}/{pr_file_name}"}
            list_arguments_filter_inline.append(arguments_filter_inline)

    multiprocess.multiprocessing_function(PRsDataManager.filter_inline_comments_check_pr, list_arguments_filter_inline,
                                          num_threads)


def clone_repos(list_repositories, cloned_path="tmp/cloned", cloned_file_dict_path=None, overwrite=False):
    print(f"Downloading repos in path {cloned_path}")
    print(f"It will generate a dict in file {cloned_file_dict_path}")

    cloned_repos_dict = {}
    for repository_name in list_repositories:
        cloned_repos_dict[repository_name] = ExtractCodeChange.clone_repository(repository_name, cloned_path,
                                                                                overwrite)
    if cloned_file_dict_path:
        json_util.save_json(cloned_file_dict_path, cloned_repos_dict)
        print(f"File {cloned_file_dict_path} saved")
    return cloned_repos_dict


def add_revised_code_to_inline_review(timeline_item, revised_code_dict):
    if timeline_item["type"] == "inlineReview":
        if timeline_item["id"] in revised_code_dict:
            timeline_item["revised_code"] = revised_code_dict[timeline_item["id"]]
        else:
            timeline_item["revised_code"] = None
    return timeline_item


def extract_revised_code_by_repository(repository_name, cloned_repository_path, prs_input_file, path_output,
                                       sample_prs=None, overwrite=False):
    print(f"Starting extract code changes for repository {repository_name}")
    repository_dir_name = repository_name.replace('/', '_')
    repository_filtered_processed_prs_files = glob.glob(f"{prs_input_file}/{repository_dir_name}/*.json")

    if sample_prs is not None:
        repository_filtered_processed_prs_files = filter(lambda pr_path: pr_path.split("/")[-1][3:-5] in sample_prs,
                                                         repository_filtered_processed_prs_files)

    for pr_file_path in repository_filtered_processed_prs_files:

        pull_request = json_util.open_json(pr_file_path)
        pr_number = pull_request["pr_number"]
        print(f"Starting search code changes in the pull request {pr_number} of {repository_name}")
        pr_with_revised_code_file_path = f"{path_output}/{repository_dir_name}/pr_{pr_number}.json"

        if os.path.isfile(pr_with_revised_code_file_path) and not overwrite:
            print(f"Skipped pull request {pr_number} of {repository_name}")
            continue

        revised_code_dict = ExtractCodeChange.search_revised_code_in_pr(pull_request, repository_name,
                                                                        cloned_repository_path)
        pr_timeline = pull_request["timeline"]
        pull_request["timeline"] = list(
            map(lambda item: add_revised_code_to_inline_review(item, revised_code_dict), pr_timeline))
        pr_with_revised_code_file_path = f"{path_output}/{repository_dir_name}/pr_{pr_number}.json"
        json_util.save_json(pr_with_revised_code_file_path, pull_request)
        print(f"Saved file of pull request {pr_number} of {repository_name} with code changes found.")


def extract_revised_code(list_repositories, cloned_repositories_path_dict, prs_input_file, path_output, num_threads=1,
                         overwrite=False):
    print(f"Extracting changes triggered by inline comments in path {prs_input_file}"
          "If pull request was processed, it will be skipped")
    print(f"Output path: {path_output}")

    list_arguments_extract_changes = []
    for repository_name in list_repositories:
        if repository_name in cloned_repositories_path_dict:
            cloned_repository_path = cloned_repositories_path_dict[repository_name]
            extract_changes_repository_arguments = {"repository_name": repository_name,
                                                    "cloned_repository_path": cloned_repository_path,
                                                    "prs_input_file": prs_input_file, "path_output": path_output,
                                                    "overwrite": overwrite}
            list_arguments_extract_changes.append(extract_changes_repository_arguments)
        else:
            print(f"It did not find the path of the repository {repository_name}")
    return multiprocess.multiprocessing_function(extract_revised_code_by_repository, list_arguments_extract_changes,
                                                 num_threads)


def clone_extract_clean_by_repository(repository_name, prs_processed_path, path_output, sample_prs=None,
                                      overwrite=False):
    repository_cloned_path_dict = clone_repos([repository_name])

    repository_cloned_path = repository_cloned_path_dict[repository_name]
    extract_revised_code_by_repository(repository_name, repository_cloned_path, prs_processed_path, path_output,
                                       sample_prs, overwrite)

    diff_repository_path = f"tmp/diffs/{repository_name.replace('/', '_')}"
    subprocess.run(["rm", "-rf", diff_repository_path, repository_cloned_path], capture_output=True,
                   universal_newlines=True)
    print(f"Finished clone, extract code change and clean for {repository_name}")


def clone_extract_clean(list_repositories, prs_processed_path, path_output, sample_path_file=1, num_threads=1,
                        overwrite=False):
    print(f"Starting the extraction of code changes of inline reviews in {prs_processed_path}")
    print(f"The output path is {path_output}")
    print(f"Threads {num_threads}")

    sample = None
    if sample_path_file is not None:
        sample = json_util.open_json(sample_path_file)

    if sample is not None:
        list_repositories = list(filter(lambda repo_name: repo_name in sample, list_repositories))

    arguments_list_clone_extract_clean = []
    for repository_name in list_repositories:

        repository_dir_name = repository_name.replace("/", "_")

        repository_prs_processed_files = glob.glob(f"{prs_processed_path}/{repository_dir_name}/*.json")
        repository_prs_processed_files = set(map(lambda file: file.split("/")[-1], repository_prs_processed_files))

        repository_prs_extracted_files = glob.glob(f"{path_output}/{repository_dir_name}/*.json")
        repository_prs_extracted_files = set(map(lambda file: file.split("/")[-1], repository_prs_extracted_files))

        if len(repository_prs_processed_files - repository_prs_extracted_files) > 0:

            sample_prs_by_repo = None
            if sample is not None:
                sample_prs_by_repo = sample[repository_name]

            clone_extract_clean_arguments = {"repository_name": repository_name,
                                             "prs_processed_path": prs_processed_path,
                                             "path_output": path_output,
                                             "sample_prs": sample_prs_by_repo,
                                             "overwrite": overwrite}
            arguments_list_clone_extract_clean.append(clone_extract_clean_arguments)

    multiprocess.multiprocessing_function(clone_extract_clean_by_repository, arguments_list_clone_extract_clean,
                                          num_threads)


def check_process_files(list_repositories, process_input, process_output):
    print(f"Checking the process from {process_input} to {process_output}")
    summary = []
    for repository_name in list_repositories:
        print(f"Analysing repository {repository_name}")
        repository_dir_name = repository_name.replace('/', '_')
        repository_input_files = glob.glob(f"{process_input}/{repository_dir_name}/*.json")
        repository_output_files = glob.glob(f"{process_output}/{repository_dir_name}/*.json")
        summary_repo = {"repository_name": repository_name,
                        "total_files_in": len(repository_input_files),
                        "total_files_out": len(repository_output_files)}
        summary.append(summary_repo)

        for pr_file_path in repository_input_files:
            pr_file_name = pr_file_path.split("/")[-1]
            output_file_name = f"{process_output}/{repository_dir_name}/{pr_file_name}"

            if output_file_name not in repository_output_files:
                print(f"The file {output_file_name} was not found")

    total_in = 0
    total_out = 0
    for summary_repo in summary:
        repository_name = summary_repo['repository_name']
        files_in = summary_repo['total_files_in']
        files_out = summary_repo['total_files_out']
        print(f"Repository {repository_name}: IN={files_in} OUT={files_out}")
        total_in = total_in + files_in
        total_out = total_out + files_out
    print(f"Total IN={total_in} and Total OUT={total_out}")


if __name__ == "__main__":

    default_tasks_output = {
        "info-repo": "data/1-prs_by_repo",
        "filter-prs": "data/2-prs_filtered",
        "details-prs": "data/3-details_prs",
        "review-threads-prs": "data/3-details_prs",
        "process-prs": "data/4-processed_prs",
        "filter-inline": "data/5-prs_after_inline_comments_filtered",
        "extract-revised-code": "data/6-prs_after_extract_revised_code",
        "clone-extract-clean": "data/6-prs_after_extract_revised_code",
        "generate-csv": "samples"
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("task", type=str, help=f"The task between: {list(default_tasks_output.keys())}")
    parser.add_argument("--repositories", "-r", type=str, required=False,
                        help="File path with repositories to be considered separated by lines")
    parser.add_argument("--input", "-i", type=str,
                        help="Path or file with data that will be used to execute the task")
    parser.add_argument("--output", "-o", type=str, help="Output path for the task")
    parser.add_argument("--threads", "-t", type=int, help="Num of threads for some tasks")
    parser.add_argument("--sleep", "-s", type=int, help="Timeout to start a new process in the task")
    parser.add_argument("--cloned", type=int,
                        help="Json where key is the repo and value the path of cloned repo")
    parser.add_argument("--sample", type=str, help="Sample to be used in generate csv")
    parser.add_argument("--start_date", type=str, help="Start date (in format YYYY-MM-DD) to be used in filter prs")
    parser.add_argument("--end_date", type=str, help="End date (in format YYYY-MM-DD) to be used in filter prs")
    parser.add_argument("--merged", type=str, help="Merged date to be used in filter prs")
    parser.add_argument("--overwrite", help="Overwrite files", action='store_true')

    args = parser.parse_args()

    list_repositories = []
    if args.repositories:
        with open(args.repositories) as repositories_file:
            list_repositories = repositories_file.read().splitlines()

    output = args.output
    if not output and args.task in default_tasks_output:
        output = default_tasks_output[args.task]

    threads = 1
    if args.threads:
        threads = args.threads

    if args.sleep:
        multiprocess.DELAY_TO_START_FUNCTION = args.sleep

    if args.task == "test":
        print(list_repositories)

    elif args.task == "clean-extra-prs":
        clean_file_prs_details(list_repositories, args.input, output)

    elif args.task == "clean-prs-errors":
        clean_file_prs_details_with_errors(list_repositories, args.input)

    elif args.task == "info-repo":
        fetch_info_reviews_repositories(args.input, output, threads)

    elif args.task == "filter-prs":
        filter_prs(list_repositories, args.input, output, threads=threads, overwrite=args.overwrite,
                   start_date_str=args.start_date, end_date_str=args.end_date, merged_str=args.merged)

    elif args.task == "details-prs":
        fetch_pr_details_repositories(list_repositories, args.input, output, threads)

    elif args.task == "review-threads-prs":
        fetch_pr_review_threads_repositories(list_repositories, args.input, output, threads)

    elif args.task == "process-prs":
        process_prs_data(list_repositories, args.input, output, threads)

    elif args.task == "filter-inline":
        filter_inline_comments_and_prs(list_repositories, args.input, output, threads)

    elif args.task == "clone-repos":
        clone_repos(list_repositories, args.input, output)

    elif args.task == "extract-revised-code":
        cloned_repositories_path = json_util.open_json(args.cloned)
        extract_revised_code(list_repositories, cloned_repositories_path, args.input,
                             output, num_threads=threads, overwrite=args.overwrite)

    elif args.task == "clone-extract-clean":
        clone_extract_clean(list_repositories, args.input, output, sample_path_file=args.sample, num_threads=threads,
                            overwrite=args.overwrite)

    elif args.task == "generate-csv":
        GenerateCSV.prs_files_to_csv(list_repositories, args.input, output, args.sample)

    elif args.task == "check-process":
        check_process_files(list_repositories, args.input, output)
