from adaptivetesting.models import ItemPool
import pandas as pd


def df_to_ip(df: pd.DataFrame) -> list[tuple[str, ItemPool]]:
    """
    Convert a DataFrame into a list of ItemPool objects,
    one per unique Module category.

    Arguments:
        - df (pd.DataFrame): A dataframe of the test questions in the format given to us in the first spreadsheet from Prof. De Melo.

    Returns:
        - a list of tuples (str, ItemPool) where each tuple contains a module name and an ItemPool of questions from just that module.
    """
    pools = []

    # Iterate through each module category
    for module, group in df.groupby("Module"):
        items_df = pd.DataFrame(
            {
                "a": group["IRT_a"].astype(float),
                "b": group["IRT_b"].astype(float),
                "c": group["IRT_c"].astype(float),
                "d": 1.0,  # 3PL upper asymptote
                "ids": group["Question_ID"].astype(int),
            }
        )

        try:
            pool = ItemPool.load_from_dataframe(items_df)
        except AttributeError:
            # Fallback for older versions
            pool = ItemPool.load_from_list(
                a=items_df["a"].to_list(),
                b=items_df["b"].to_list(),
                c=items_df["c"].to_list(),
                d=items_df["d"].to_list(),
                ids=items_df["ids"].to_list(),
            )

        # You might want to store the module name alongside the pool
        pools.append((module, pool))

    return pools
