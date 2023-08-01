from typing import Optional


def gen_prediction_tweet(
    pred_winner: str,
    pred_loser: str,
    time: str,
    venue: str,
    winning_odds: Optional[str] = None,
    losing_odds: Optional[str] = None,
    winning_odds_bookmaker: Optional[str] = None,
    losing_odds_bookmaker: Optional[str] = None,
) -> str:
    if winning_odds and losing_odds:
        losing_odds = (
            ("+" + str(losing_odds)) if (int(losing_odds) > 100) else str(losing_odds)
        )
        winning_odds = (
            ("+" + str(winning_odds))
            if (int(winning_odds) > 100)
            else str(winning_odds)
        )
    msg = f"I predict the {pred_winner} "
    if winning_odds and winning_odds_bookmaker:
        msg += f"({str(winning_odds)} on {winning_odds_bookmaker}) "
    msg += f"will defeat the {pred_loser} "
    if losing_odds and losing_odds_bookmaker:
        msg += f"({str(losing_odds)} on {losing_odds_bookmaker}) "
    msg += f"today at {time} ET at {venue}."
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
        f"for a prediction accuracy of {percentage}. "
    )
    if is_upset:
        msg += (
            f"Among these predictions, I had correctly anticipated the {upset_winner} "
            f"(+{upset_winner_odds}) defeating the {upset_loser} ({upset_loser_odds}) "
            f"(Odds from about 1 hour before game start)"
        )
    return msg
