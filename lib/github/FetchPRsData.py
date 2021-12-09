from .GitHubFetcher import GitHubGraphQLFetcher, UnknownError
import os
from datetime import datetime, timedelta
from ..utils import file_json_utils as json_util

MAX_LIMIT_RESOURCES = 1000


def print_info_request(repository_fetcher, all_responses, num_resources, name_resource):
    print(f"retries {repository_fetcher.retries}/{repository_fetcher.max_retries}")
    print(f"fetched {len(all_responses)} pages and {num_resources} {name_resource}")
    remaining = json_util.get_path_in_dict(repository_fetcher.response, "data.rateLimit.remaining")
    reset_at = json_util.get_path_in_dict(repository_fetcher.response, "data.rateLimit.resetAt")
    total_cost = sum(
        json_util.get_path_in_dict(response, "data.rateLimit.cost") for response in all_responses)
    print(f"Total cost: {total_cost}. Remaining:{remaining}. Reset at:{reset_at}")


def fetch_pull_request(repository_name, save_file_path, created_at_from, created_at_to, query_file_path,
                       overwrite=False):
    if os.path.isfile(save_file_path) and not overwrite:
        print(f"Skipped fetching prs to {save_file_path}")
        return True

    date_format = "%Y-%m-%d"
    field_created = f"{created_at_from.strftime(date_format)}..{created_at_to.strftime(date_format)}"
    query_fields = {"repository_fullname": repository_name, "created": field_created}
    repository_fetcher = GitHubGraphQLFetcher(query_file_path=query_file_path,
                                              query_fields=query_fields,
                                              page_info_path="data.search.pageInfo",
                                              after_page_query_field="after",
                                              file_save_path=save_file_path,
                                              timeout=2,
                                              max_retries=10)

    response = repository_fetcher.run()
    if json_util.get_path_in_dict(response, "data.search.issueCount") > MAX_LIMIT_RESOURCES:
        middle_date = created_at_from + (created_at_to - created_at_from) / 2
        middle_date_next_day = middle_date + timedelta(days=1)

        save_file_path_dir = "/".join(save_file_path.split("/")[:-1])
        repository_name_to_file = repository_name.replace("/", "_")

        save_file_path_middle_down = f"{save_file_path_dir}/{repository_name_to_file}"
        save_file_path_middle_down += f"_F{created_at_from.strftime(date_format)}T{middle_date.strftime(date_format)}.json"
        fetch_pull_request(repository_name, save_file_path_middle_down, created_at_from, middle_date, query_file_path,
                           overwrite)

        save_file_path_middle_up = f"{save_file_path_dir}/{repository_name_to_file}"
        save_file_path_middle_up += f"_F{middle_date_next_day.strftime(date_format)}T{created_at_to.strftime(date_format)}.json"
        fetch_pull_request(repository_name, save_file_path_middle_up, middle_date_next_day, created_at_to,
                           query_file_path, overwrite)

    else:
        pull_requests_node_path = "data.search.nodes"
        print(
            f"\nStarting run {repository_name}, from {created_at_from.strftime(date_format)} to {created_at_to.strftime(date_format)}")
        all_responses = repository_fetcher.run_for_all_pages()
        all_responses_structured = repository_fetcher.save_all_responses_structured(pull_requests_node_path)
        total_prs = len(json_util.get_path_in_dict(all_responses_structured, pull_requests_node_path))
        print(
            f"saved run {repository_name}, from {created_at_from.strftime(date_format)} to {created_at_to.strftime(date_format)}")
        print_info_request(repository_fetcher, all_responses, total_prs, "prs")

    return True


def get_info_prs_of_repository(repository_name, repository_createat, output_path, overwrite=False):
    owner, name = repository_name.split("/")
    save_file_path = f"{output_path}/{owner}_{name}.json"
    query_file_path = "queries/fetch_repository_prs_info.query"

    created_at_from = datetime.fromisoformat(repository_createat)
    created_at_to = datetime(2021, 10, 1)

    return fetch_pull_request(repository_name, save_file_path, created_at_from, created_at_to,
                              query_file_path, overwrite)


def fetch_pull_request_data(owner, name, pr_number, save_file_path, query_file_path, page_info_path,
                            pull_requests_node_path, overwrite=False):
    if os.path.isfile(save_file_path) and not overwrite:
        print(f"Skipped fetching prs to {save_file_path}")
        return True

    repository_name = f"{owner}/{name}"
    query_fields = {"owner": owner, "name": name, "pr_number": str(pr_number)}
    repository_fetcher = GitHubGraphQLFetcher(query_file_path=query_file_path,
                                              query_fields=query_fields,
                                              page_info_path=page_info_path,
                                              after_page_query_field="after",
                                              file_save_path=save_file_path,
                                              timeout=5,
                                              max_retries=10)

    try:
        print(f"\nStarting run {repository_name}/{pr_number}")
        all_responses = repository_fetcher.run_for_all_pages()
        all_responses_structured = repository_fetcher.save_all_responses_structured(pull_requests_node_path)
        total_items = len(json_util.get_path_in_dict(all_responses_structured, pull_requests_node_path))
        print(f"saved {repository_name}/{pr_number}")
        print_info_request(repository_fetcher, all_responses, total_items, "items")
        return True
    except Exception as e:
        print(f"Something happened wrong when running for {repository_name}/{pr_number}")
        print(e)
        return False


def fetch_pull_request_details(owner, name, pr_number, save_file_path, overwrite=False):
    query_file_path = "queries/fetch_prs_data_by_pr.query"
    page_info_path = "data.repository.pullRequest.timelineItems.pageInfo"
    pull_requests_node_path = "data.repository.pullRequest.timelineItems.nodes"
    return fetch_pull_request_data(owner, name, pr_number, save_file_path, query_file_path, page_info_path,
                                   pull_requests_node_path, overwrite)


def fetch_pull_request_review_threads(owner, name, pr_number, save_file_path, overwrite=False):
    query_file_path = "queries/fetch_review_threads_by_pr.query"
    page_info_path = "data.repository.pullRequest.reviewThreads.pageInfo"
    pull_requests_node_path = "data.repository.pullRequest.reviewThreads.nodes"
    return fetch_pull_request_data(owner, name, pr_number, save_file_path, query_file_path, page_info_path,
                                   pull_requests_node_path, overwrite)
