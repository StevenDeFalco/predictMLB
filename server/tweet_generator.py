def gen_prediction_tweet(
    pred_winner: str,
    pred_loser: str,
    time: str,
    venue: str,
    winning_odds: str,
    losing_odds: str,
    winning_odds_bookmaker: str,
    losing_odds_bookmaker: str,
) -> str:
    # TODO: unique a.i. text generation
    # placeholder tweet format below until implemented
    msg = (
        f"I predict the {pred_winner} ({winning_odds} on {winning_odds_bookmaker}) "
        f"will defeat the {pred_loser} ({losing_odds} on {losing_odds_bookmaker}) "
        f"at {time} when the two teams match up at {venue}."
    )
    return msg


def gen_result_tweet(
    correct_wrong: str,
    percentage: str,
    is_upset: bool,
    upset_winner: str,
    upset_loser: str,
    upset_winner_odds: str,
    upset_loser_odds: str,
) -> str:
    msg = (
        f"Of yesterday's MLB games, I predicted {correct_wrong} correctly, "
        f"and thus had a prediction accuracy of {percentage}. "
    )
    if is_upset:
        msg += (
            f"Among these predictions, I had correctly anticipated the {upset_winner} "
            f"(+{upset_winner_odds}) defeating the {upset_loser} ({upset_loser_odds}) "
            f"(Odds are from the time of my tweeted prediction)."
        )
    return msg
