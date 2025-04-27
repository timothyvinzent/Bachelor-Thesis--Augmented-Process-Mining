import pandas as pd

def save_report_v2(output,scores,filename, program, e_metric):
    qs = []
    exs = []
    preds = []
    for i in range(len(output)):
        qs.append(output[i][0]["question"])
        exs.append(output[i][0]["example"])
        try:
            preds.append(output[i][1]["answer"])
        except:
            preds.append("No Answer Possible")

    qa, es, tb= program.pm_sql.get_history()
    re = e_metric.get_reasoning()
    ct = program.get_col_tracked()

    df_merged = pd.DataFrame({"question": qs, "example": exs, "prediction": preds, "SCORE": scores})
    df_merged["col_selection"] = df_merged["question"].map(ct)
    df_merged['reasoning'] = df_merged['question'].map(re)
    df_merged['queries'] = df_merged['question'].map(qa)
    df_merged['errors'] = df_merged['question'].map(es)
    df_merged['table'] = df_merged['question'].map(tb)
    #df_merged.to_csv(f"{filename}.csv", index=False)
    # Initialize counters
    TP = FP = TN = FN = 0

    # Iterate through the value_counts result
    for index, count in df_merged["col_selection"].value_counts().items():
        last_label = index[-1]  # Get the last label directly from the list
        if last_label == 'TP':
            TP += count
        elif last_label == 'FP':
            FP += count
        elif last_label == 'TN':
            TN += count
        elif last_label == 'FN':
            FN += count

    # Calculate metrics with error handling
    try:
        precision = TP / (TP + FP) if (TP + FP) > 0 else 0
        recall = TP / (TP + FN) if (TP + FN) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (TP + TN) / (TP + TN + FP + FN) if (TP + TN + FP + FN) > 0 else 0
    except ZeroDivisionError:
        precision = recall = f1 = accuracy = 0

    # create additional dataframe columns for the metrics in df_merged
    df_merged["precision"] = precision
    df_merged["recall"] = recall
    df_merged["f1"] = f1
    df_merged["accuracy"] = accuracy
    df_merged.to_csv(f"{filename}.csv", index=False)


    return df_merged


def save_report_isolated(output,scores,filename, program, e_metric):
    qs = []
    exs = []
    preds = []
    for i in range(len(output)):
        qs.append(output[i][0]["question"])
        exs.append(output[i][0]["example"])
        try:
            preds.append(output[i][1]["answer"])
        except:
            preds.append("No Answer Possible")

    qa, es, tb, rh = program.get_history()
    re = e_metric.get_reasoning()

    df_merged = pd.DataFrame({"question": qs, "example": exs, "prediction": preds, "SCORE": scores})
    df_merged['reasoning'] = df_merged['question'].map(re)
    df_merged['queries'] = df_merged['question'].map(qa)
    df_merged['errors'] = df_merged['question'].map(es)
    df_merged['table'] = df_merged['question'].map(tb)
    df_merged['reasoning_hist'] = df_merged['question'].map(rh)
    df_merged.to_csv(f"{filename}.csv", index=False)
    return df_merged