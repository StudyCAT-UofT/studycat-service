import sys
from pathlib import Path

# Add the project root (studycat-service) to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
from load_excel import excel_to_df
from load_item_pool import df_to_ip
from models.unidimensional import UnidimensionalModel
from models.multidimensional import MultidimensionalModel
from adaptivetesting.models import TestItem, ItemPool


def run_interactive_cat():
    file_path = input("Enter the file path to the Excel spreadsheet: ").strip()
    df = excel_to_df(file_path)

    item_pools = df_to_ip(df)

    multi_model = MultidimensionalModel(1, 1)

    for item_pool in item_pools:
        # create a model for each module
        multi_model.add_model(item_pool[0], 1.0, item_pool[1])

    print("Successfully loaded and created models!")

    # makes lookup with Question_ID easier
    df.set_index("Question_ID", inplace=True)

    while True:
        next_question = multi_model.get_next_item()

        question_row = df.loc[next_question.id]

        print("This is a question from: " + question_row["Module"])

        print(
            "\nYour current estimated theta value for this module is: "
            + str(multi_model.get_theta(question_row["Module"]))
            + "\n"
        )

        print(question_row["Stem"])

        print("Responses:")
        print("A: " + question_row["Response_A"])
        print("B: " + question_row["Response_B"])
        print("C: " + question_row["Response_C"])
        print("D: " + question_row["Response_D"])

        print("Correct response: " + question_row["Correct_Answer"])

        response = int(input("Enter 1 for correct, 0 for incorrect"))

        multi_model.record_response(question_row["Module"], response, next_question)

        print(
            "Response recorded. New theta value for "
            + question_row["Module"]
            + ": "
            + str(multi_model.get_theta(question_row["Module"]))
        )

        quit = int(input("Enter 1 to quit. "))

        if quit == 1:
            break

    print("Final theta values: ")
    for item_pool in item_pools:
        print(item_pool[0] + ": " + str(multi_model.get_theta(item_pool[0])))


if __name__ == "__main__":
    run_interactive_cat()
