from ..utils import file_json_utils
import requests
import re
import time


def replace_parser(key, dict_parser):
    value = file_json_utils.get_path_in_dict(dict_parser, key[2:-1])
    if not value:
        value = ""
    return value


class RateLimit(Exception):
    pass

class UnknownError(Exception):
    pass


class GitHubGraphQLFetcher:

    def __init__(self, query_file_path=None, query_fields=None, file_save_path=None, page_info_path=None,
                 after_page_query_field=None, success_request_callback=None, stop_criteria_function=None,
                 max_retries=10, timeout=1,
                 config_file="config.json",
                 meta_fields_file="queries/meta_fields.json"):
        self.file_save_path = file_save_path
        self.config = file_json_utils.open_json(config_file)
        self.meta_fields = file_json_utils.open_json(meta_fields_file)

        self.query_file_path = query_file_path
        self.query = None
        self.previous_query = None
        self.query_fields = query_fields
        if self.query_file_path:
            self.query = self.mount_query(query_file_path, query_fields)

        self.page_info_path = page_info_path
        self.after_page_query_field = after_page_query_field

        self.stop_criteria_function = stop_criteria_function
        self.success_request_callback = success_request_callback

        self.token_index = 0

        self.retries = 0
        self.max_retries = max_retries
        self.timeout = timeout

        self.response = None
        self.previous_responses = None

    def __iter__(self):
        self.response = None
        self.previous_responses = None
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if not self.page_info_path:
            raise Exception("The attribute page_info_path was not defined")
        if not self.after_page_query_field:
            raise Exception("The attribute after_page_query_field was not defined")

        if not self.previous_responses:
            self.previous_responses = []

        if not self.previous_query:
            self.previous_query = []

        if self.query:
            self.previous_query.append(self.query)

        if self.response:

            if self.stop_criteria_function:
                if self.stop_criteria_function(self.response):
                    raise StopIteration()

            if not file_json_utils.get_path_in_dict(self.response, f"{self.page_info_path}.hasNextPage"):
                raise StopIteration()

            self.previous_responses.append(self.response)
            new_query_fields = self.query_fields
            end_cursor = file_json_utils.get_path_in_dict(self.response, f"{self.page_info_path}.endCursor")
            new_query_fields[self.after_page_query_field] = f"after:\"{end_cursor}\""
            self.mount_query(self.query_file_path, new_query_fields)

        return self.run()

    def run_for_all_pages(self):
        for _ in self:
            pass
        return self.all_responses()

    def run(self, previous_error=None):
        if self.token_index >= len(self.config['github']['tokens']):
            raise RateLimit(f"You used all limit to all tokens, consider wait and run again.\n{previous_error}")
        headers = {"Authorization": f"token {self.config['github']['tokens'][self.token_index]}"}

        try:
            request = requests.post(self.config['github']['graphql'], json={'query': self.query}, headers=headers)
        except requests.exceptions.ChunkedEncodingError as e:
            self.retries = self.retries + 1
            time.sleep(self.timeout)
            return self.run(e)

        if request.status_code == 200:
            if "errors" in request.json():
                self.token_index = self.token_index + 1
                return self.run(request.json())
            else:
                self.retries = 0
                self.response = request.json()
                if self.success_request_callback:
                    self.success_request_callback(request, self)
                return self.response
        if (request.status_code == 502 or request.status_code == 403) and self.retries < self.max_retries:
            print(f"RateLimitExceeded: {request.json()}")
            print(f"It will wait for {self.timeout}s and try again")
            self.retries = self.retries + 1
            time.sleep(self.timeout)
            return self.run()
        else:
            raise UnknownError(f"Query failed to run by returning code of {request.status_code}.\n"
                               f"Retries: {self.retries}/{self.max_retries}.\n"
                               f"Result: {request.json()}")

    def mount_query(self, query_file_path, query_fields=None):
        with open(query_file_path) as query_file:
            query_data = query_file.read()
        if self.meta_fields:
            query_fields = query_fields | self.meta_fields
        self.query = re.sub(r'f{([^}])+}', lambda match: replace_parser(match.group(), query_fields), query_data)
        return self.query

    def open_response(self, path=None):
        if not path:
            path = self.file_save_path
        self.response = file_json_utils.open_json(path)

    def save_response(self, path=None):
        if not path:
            path = self.file_save_path
        file_json_utils.save_json(path, self.response)

    def all_responses(self):
        if not self.previous_responses:
            return [self.response]
        else:
            return self.previous_responses + [self.response]

    def all_responses_structured(self, merge_nodes_in_path):
        all_responses = self.response.copy()
        if self.previous_responses:
            nodes_merged = file_json_utils.get_path_in_dict(all_responses, merge_nodes_in_path)
            for actual_response in reversed(self.previous_responses):
                nodes_merged.extend(file_json_utils.get_path_in_dict(actual_response, merge_nodes_in_path))
        return all_responses

    def save_all_responses(self, path=None):
        if not path:
            path = self.file_save_path

        all_responses = self.all_responses()
        file_json_utils.save_json(path, all_responses)
        return all_responses

    def save_all_responses_structured(self, merge_nodes_in_path, path=None):
        if not path:
            path = self.file_save_path

        all_responses = self.all_responses_structured(merge_nodes_in_path)
        file_json_utils.save_json(path, all_responses)
        return all_responses
