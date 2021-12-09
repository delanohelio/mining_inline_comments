from ..utils import file_json_utils as json_util


def get_review_threads_by_pr(pr_detail_file_path):

    reply_review_inline_comment_template = {"id": "id", "url": "url", "bodyText": "bodyText", "author": "author.login",
                                      "createdAt": "createdAt", "replyToReviewId": "replyTo.id"}

    replies_by_comment_id = {}
    review_threads_pr_data = json_util.open_json(pr_detail_file_path)

    if review_threads_pr_data:
        review_threads_items = json_util.get_path_in_dict(review_threads_pr_data,
                                                          "data.repository.pullRequest.reviewThreads.nodes")
        inline_comments = [inline_comment for review_thread in review_threads_items for inline_comment in
                           review_thread["comments"]["nodes"]]
        inline_comments_with_reply_to = filter(lambda comment: comment["replyTo"] is not None, inline_comments)
        for inline_comment in inline_comments_with_reply_to:
            inline_comment = json_util.extract_keys_in_dict(inline_comment, reply_review_inline_comment_template)
            inline_comment_reply_to = inline_comment["replyToReviewId"]

            if inline_comment_reply_to not in replies_by_comment_id:
                replies_by_comment_id[inline_comment_reply_to] = []

            replies_by_comment_id[inline_comment_reply_to].append(inline_comment)

    return replies_by_comment_id


def process_prs_data_by_pr(pr_detail_file_path, pr_review_details_file_path=None, output_file_path=None):
    pull_request_template = {"pr_number": "data.repository.pullRequest.number",
                             "pr_title": "data.repository.pullRequest.title",
                             "pr_createdAt": "data.repository.pullRequest.createdAt",
                             "pr_url": "data.repository.pullRequest.url"}

    review_inline_comment_template = {"id": "id", "url": "url", "bodyText": "bodyText", "author": "author.login",
                                      "createdAt": "createdAt", "path": "path", "diffHunk": "diffHunk",
                                      "originalCommit": "originalCommit.oid", "replyToReviewId": "replyTo.id"}
    force_pushed_template = {"oid": "afterCommit.oid", "url": "afterCommit.url", "message": "afterCommit.message",
                             "committedDate": "afterCommit.committedDate"}
    commit_template = {"oid": "commit.oid", "url": "commit.url", "message": "commit.message",
                       "committedDate": "commit.committedDate"}

    pr_data = json_util.open_json(pr_detail_file_path)

    pr_processed_data = json_util.extract_keys_in_dict(pr_data, pull_request_template)

    timeline_items = json_util.get_path_in_dict(pr_data, "data.repository.pullRequest.timelineItems.nodes")

    replies_in_review_threads = None
    if pr_review_details_file_path:
        replies_in_review_threads = get_review_threads_by_pr(pr_review_details_file_path)

    timeline_items_processed_list = []
    print(f"Processing file {pr_detail_file_path}")
    for item in timeline_items:
        if item["__typename"] == "PullRequestReview":
            review_inline_comments_list = item["comments"]["nodes"]
            review_inline_comments_list = list(map(lambda inline:
                                                   json_util.extract_keys_in_dict(inline,
                                                                                  review_inline_comment_template),
                                                   review_inline_comments_list))

            if replies_in_review_threads is not None:
                review_inline_comments_list = list(filter(lambda comment: comment["replyToReviewId"] is None,
                                                               review_inline_comments_list))
                for inline_comment in review_inline_comments_list:
                    inline_comment_id = inline_comment["id"]
                    inline_comment["replies"] = None
                    if inline_comment_id in replies_in_review_threads:
                        inline_comment["replies"] = replies_in_review_threads[inline_comment_id]

            review_inline_comments_list = [dict(inline, **{'type': 'inlineReview'}) for inline in
                                           review_inline_comments_list]
            timeline_items_processed_list.extend(review_inline_comments_list)
        elif item["__typename"] == "HeadRefForcePushedEvent":
            force_pushed_data_processed = json_util.extract_keys_in_dict(item, force_pushed_template)
            force_pushed_data_processed["type"] = "forcePushed"
            timeline_items_processed_list.append(force_pushed_data_processed)
        else:
            commit_data_processed = json_util.extract_keys_in_dict(item, commit_template)
            commit_data_processed["type"] = "commit"
            timeline_items_processed_list.append(commit_data_processed)

    pr_processed_data["timeline"] = timeline_items_processed_list
    if output_file_path:
        json_util.save_json(output_file_path, pr_processed_data)
        print(f"Saved processed pr in {output_file_path}")

    return pr_processed_data


def filter_inline_comments_check_pr(processed_pr_file_path, validate_timeline_item_function, validate_pr_function,
                                    output_file_path=None):
    print(f"Evaluating pull request in {processed_pr_file_path}")
    pull_request = json_util.open_json(processed_pr_file_path)
    timeline_pr = pull_request["timeline"]
    pull_request["timeline"] = list(filter(validate_timeline_item_function, timeline_pr))

    if not validate_pr_function(pull_request):
        print(f"Pull request {processed_pr_file_path} not validate")
        return None

    if output_file_path:
        json_util.save_json(output_file_path, pull_request)
        print(f"Pull request saved in {output_file_path}")

    return pull_request
