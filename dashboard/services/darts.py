import requests

# For now, exception handler will be here and only printing
def _handle_exception(ex):
        print('---------------------------------------')
        print('Exception:')
        print('---------------------------------------')
        print(ex)
        print('---------------------------------------')


def _get_darts_scores(game: str) -> list:
    try:
        url = "http://home.dev.com/api/v1/darts?page=1&limit=1000"
        response = requests.get(url)
        data = response.json()

        # Filter for the game
        filtered_data = [d for d in data if d['game'] == game]

        # Prepare data for the chart
        avg_scores = [round(d['avg_3_dart_score'], 2) for d in filtered_data]  # y-axis
    except Exception as ex:
        _handle_exception(ex)
    return avg_scores


# ---------- Wrappers ----------
def collect_dart_summary():
    dart_avg_scores_501 = _get_darts_scores("501 - single out")
    dart_avg_scores_score_training = _get_darts_scores("score training")    
    return dart_avg_scores_501, dart_avg_scores_score_training

    