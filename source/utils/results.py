from datetime import datetime

user_entry = {'user_id': 0,
              'profile_pic_url': '',
              'username': '',
              'name': '',
              'description': "Twitter User not found",
              'location': None,
              'external_url': '',
              'timestamp': datetime.now().timestamp(),
              'is_verified': False,
              'number_of_tweets': 0,
              'following_count': 0,
              'follower_count': 0}


def format_results(results):
    if results['status'] == 'Succeeded':
        return {"username": results['username'], "results": {key: value for key, value in results.items() if key not in ['fail_reason', 'username', 'id']}}
    elif results['status'] == 'Failed':
        if results['fail_reason'] == "Twitter User not found":
            return {"username": results['username'], "results": "Twitter User not found"}
        else:
            return {"username": results['username'], "results": {key: value for key, value in results.items() if key not in ['username', 'id', 'status', 'fail_reason']}}
    else:
        # return {"username": results['username'], "results": results['status']}
        return {"username": results['username'], "results": {key: value for key, value in results.items() if key not in ['username', 'id', 'status', 'fail_reason']}}