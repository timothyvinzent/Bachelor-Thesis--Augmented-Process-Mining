import chromadb
import re
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
#from chromadb.utils import embedding_functions
#sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-mpnet-base-v2")

docs_full = """- 'amount' (int): The amount due to be paid for the fine (including the penalty amount in case it is added). There are no nan values in this column.
- 'org_resource' (int): A numeric code indicating the employee who handled the case.
- 'dismissal' (string): A flag indicating whether and by whom the fine is dismissed. It is initialized to NIL. We know the meaning of:  
        'G': dismissed by the judge
        '#': dismissed by the prefecture
        NIL: not dismissed, i.e., to be paid.
        There are several other values used for which we do not know the semantics.
- 'concept_name' (string): the activity/ event type name
    Activity Description, column: 'concept_name':
        > 'Create Fine': The initial creation of the fine in the information system. It initializes event log attributes amount, dismissal, points and totalPaymentAmount.
        > 'Send Fine': A notification about the fine is sent by post to the offender.
        > 'Insert Fine Notification': The notification is received by the offender.
        > 'Add penalty': An additional penalty is applied.
        > 'Payment': A payment made by the offender is registered.
        > 'Send for Credit Collection': Unpaid fines are sent for credit collection. A separate process is started by a collection agency to collect the money of the unpaid fines.
        > 'Insert Date Appeal to Prefecture': The offender appeals against the fine to the prefecture. A prefecture in Italy is an administrative body representing the national government in each province.
        > 'Send Appeal to Prefecture': The appeal is sent to the prefecture by the local police.
        > 'Receive Result Appeal from Prefecture': The local police receives the result of the appeal. If the prefecture dismisses the fine, the appeal is deemed accepted, and the obligation to pay the fine is cancelled. In this case, there is no need for the police to receive the result from the prefecture (Receive Result Appeal from Prefecture) and notify the offender (Notify Result Appeal to Offender).
        > 'Notify Result Appeal to Offender': The local police informs the offender of the appeal result. 
        > 'Appeal to Judge': The offender appeals against the fine to a judge.
    IMPORTANT: The last event in a case can be arbitrary. There is no guarantee that the last event is 'Send Fine' or 'Payment'. The last event can be any event in the log.
- 'vehicleClass' (string): A flag indicating the kind of vehicle driven or owned by the offender. The semantics of the values is unknown.
- 'totalPaymentAmount' (int): The cumulative amount paid by the offender. It is always initialized to 0. There are no nan values in this column.
- 'lifecycle_transition' (string): the transition of the activity (complete, start, etc.)
- 'article' (string): The number of the article of the Italian roadtraffic law that is violated by the offender (e.g., article 157 refers to stopping and parking vehicles).
- 'points' (float): Penalty points deducted from the driving license. In Italy, each driver starts with 20 points on their license and may loose points for each offence, based on the gravity.
- 'expense' (int): The additional amount due to be paid for postal expenses. There are no nan values in this column.
- 'notificationType' (string): A flag indicating to whom the fine refers. 'P': car owner, 'C': car driver.
- 'lastSent' (datetime): N/A
- 'paymentAmount' (int): The amount paid by the offender in one transaction. There are no nan values in this column.
- 'matricola' (string): N/A (Probably refers to the matriculation number of the car.)
- 'dismissed_by_prefecture' (int): A boolean indicator (stored as an integer) showing whether the fine was dismissed by the prefecture ('#') across all events of a case. 1 for dismissed by the prefecture, 0 otherwise.
- 'dismissed_by_judge' (int): A boolean indicator (stored as an integer) showing whether the fine was dismissed by a judge ('G') across all events of a case. 1 for dismissed by the judge, 0 otherwise.
- 'maxtotalPaymentAmount' (int): The maximum total payment amount recorded for each case. If all entries are NaN or Null, the value is set to 0. This value is consistent across all rows pertaining to the same case.
- 'duration' (int): The total duration in seconds between the first and last event for each case, consistent across all rows pertaining to the same case.
- 'event_count' (int): The number of events recorded for each case, consistent across all rows pertaining to the same case.
- 'expense_sum' (int): The total sum of 'expense' values for each case, consistent across all rows pertaining to the same case.
- 'amount_min' (int): The minimum non zero and non null 'amount' value recorded for each case, consistent across all rows pertaining to the same case.
- 'amount_last' (int): The maximum 'amount' value recorded for each case, consistent across all rows pertaining to the same case.
- 'dismissed' (int): A boolean indicator (stored as an integer) showing whether the fine was dismissed by either the judge ('G') or the prefecture ('#') across all events of a case. 1 for dismissed, 0 otherwise.
- 'credit_collected' (int): A boolean indicator (stored as an integer) showing whether any event in a case involves sending the fine for credit collection ('Send for Credit Collection'). 1 if any event in the case involves credit collection, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'obligation_topay_cancelled' (int): A boolean indicator (stored as an integer) showing whether the obligation to pay the fine is cancelled due to the time difference between 'Create Fine' and 'Send Fine' being more than 90 days. 1 for cancelled, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'penalty_added' (int): A boolean indicator (stored as an integer) showing whether any event in a case involves adding a penalty ('Add penalty'). 1 if any event in the case involves adding a penalty, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'dismissed_by_other' (int): A boolean indicator (stored as an integer) showing whether any dismissal record in a case does not match the predefined values (NaN, NULL, NIL, G, or #). 1 if there is at least one such record, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'appealed_to_judge' (int): A boolean indicator (stored as an integer) showing whether any event in a case involves an appeal to a judge ('Appeal to Judge'). 1 if any event in the case involves an appeal to a judge, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'appealed_to_prefecture' (int): A boolean indicator (stored as an integer) showing whether any event in a case involves an appeal to the prefecture ('Insert Date Appeal to Prefecture'). 1 if any event in the case involves an appeal to the prefecture, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'appeal_to_judgeorprefecture' (int): A boolean indicator (stored as an integer) showing whether any event in a case involves an appeal to a judge ('Appeal to Judge') or an appeal to the prefecture ('Insert Date Appeal to Prefecture'). 1 if any event in the case involves either, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'add_penalty_count' (int): The number of times the event 'Add penalty' occurs for each case, consistent across all rows pertaining to the same case.
- 'send_fine_count' (int): The number of times the event 'Send Fine' occurs for each case, consistent across all rows pertaining to the same case.
- 'payment_count' (int): The number of times the event 'Payment' occurs for each case, consistent across all rows pertaining to the same case.
- 'insert_fine_notification_count' (int): The number of times the event 'Insert Fine Notification' occurs for each case, consistent across all rows pertaining to the same case.
- 'send_for_credit_collection_count' (int): The number of times the event 'Send for Credit Collection' occurs for each case, consistent across all rows pertaining to the same case.
- 'insert_date_appeal_to_prefecture_count' (int): The number of times the event 'Insert Date Appeal to Prefecture' occurs for each case, consistent across all rows pertaining to the same case.
- 'send_appeal_to_prefecture_count' (int): The number of times the event 'Send Appeal to Prefecture' occurs for each case, consistent across all rows pertaining to the same case.
- 'receive_result_appeal_from_prefecture_count' (int): The number of times the event 'Receive Result Appeal from Prefecture' occurs for each case, consistent across all rows pertaining to the same case.
- 'notify_result_appeal_to_offender_count' (int): The number of times the event 'Notify Result Appeal to Offender' occurs for each case, consistent across all rows pertaining to the same case.
- 'appeal_to_judge_count' (int): The number of times the event 'Appeal to Judge' occurs for each case, consistent across all rows pertaining to the same case.
- 'outstanding_balance' (int): The final balance calculated for each case, derived from the last amount due ('amount_last') plus the sum of expenses ('expense_sum') minus the maximum total payment amount ('maxtotalPaymentAmount'). This value is consistent across all rows pertaining to the same case.
- 'credit_collected_AND_dismissed' (int): A boolean indicator (stored as an integer) showing whether any event in a case involves both dismissal of the fine and credit collection. 1 if any event in the case involves both, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'paid_nothing' (int): A boolean indicator (stored as an integer) showing whether the maximum total payment amount for each case is zero or less. 1 if the maximum total payment amount is zero or less, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'appeal_judge_cancelled' (int): A boolean indicator (stored as an integer) showing whether a case was appealed to a judge and not dismissed by the judge. 1 for cases where the appeal to the judge was not dismissed, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'appeal_prefecture_cancelled' (int): A boolean indicator (stored as an integer) showing whether a case was appealed to the prefecture and not dismissed by the prefecture. 1 for cases where the appeal to the prefecture was not dismissed, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'fully_paid' (int): A boolean indicator (stored as an integer) showing whether the outstanding balance for each case is zero or less, indicating that the fine has been fully paid. 1 for fully paid, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'overpaid' (int): A boolean indicator (stored as an integer) showing whether the outstanding balance for each case is less than zero, indicating that the payment exceeded the amount due. 1 for overpaid, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'underpaid' (int): A boolean indicator (stored as an integer) showing whether the outstanding balance for each case is greater than zero, indicating that the fine has not been fully paid. 1 for underpaid, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'credit_collected_AND_fully_paid' (int): A boolean indicator (stored as an integer) showing whether any event in a case involves both credit collection ('Send for Credit Collection') and full payment of the fine. 1 if any event in the case involves both, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'dismissed_AND_fully_paid' (int): A boolean indicator (stored as an integer) showing whether any event in a case involves both the dismissal of the fine and the full payment of the fine. 1 if any event in the case involves both, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'overpaid_amount' (int): The amount by which the payment exceeded the amount due, calculated as the absolute value of the negative 'outstanding_balance' if 'overpaid' is true (1), otherwise set to 0. This value is consistent across all rows pertaining to the same case.
- 'underpaid_amount' (int): The amount still owed if the fine has not been fully paid, equal to the 'outstanding_balance' when 'underpaid' is true (1), otherwise set to 0. This value is consistent across all rows pertaining to the same case.
- 'part_paid' (int): A boolean indicator (stored as an integer) showing whether the fine is partially paid, i.e., not fully paid and not unpaid. It is set to 1 if both 'fully_paid' and 'paid_nothing' are 0, indicating partial payment, and 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'unresolved' (int): A boolean indicator (stored as an integer) showing whether a case remains unresolved, i.e., not fully paid, not collected for credit, and not dismissed. 1 for unresolved, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'paid_without_obligation' (int): A boolean indicator (stored as an integer) showing whether the obligation to pay the fine was cancelled and the fine was fully paid for each case. 1 if both conditions are met, 0 otherwise. This value is consistent across all rows pertaining to the same case.
- 'time_timestamp_beginn' (datetime): The timestamp of the first event for each case, consistent across all rows pertaining to the same case.
- 'time_timestamp_end' (datetime): The timestamp of the last event for each case, consistent across all rows pertaining to the same case."""

class Chroma():
    def __init__(self, sentence_transformer_ef, documentation = docs_full):
        self.documentation = documentation
        self.client = chromadb.Client()
        try:
            self.client.delete_collection("my_collection")
        except:
            pass
        try:
            self.collection = self.client.create_collection(name="my_collection", embedding_function=sentence_transformer_ef, metadata={"hnsw:space": "cosine"})
        except:
            self.collection = self.client.get_collection(name="my_collection", embedding_function=sentence_transformer_ef)

        self.default = """THE DATABASE CONTAINS THE TABLE: event_log CONTAINING THE FOLLOWING COLUMNS (only the ones denoted by a "-", )
- 'case_concept_name' (string): the case identifier, use this to group by cases (retrieve information about cases as a whole)
- 'time_timestamp' (datetime): the timestamp of the activity."""
        self.docs = self.split_string_into_list()
        print(self.docs)
        self.cols = self.add_columns()
        self.ids = []
        for i in range(len(self.cols)):
            self.ids.append(str(i))
        self.metadata = []
        for i in self.cols:
            self.metadata.append({"columns": i})
        self.add_init()
        

    def split_string_into_list(self):
        # Split the string at each occurrence of the "-" character.
        # This will not include the "-" in the resulting list items, so we need to add it back.
        parts = self.documentation.split('-')
        # Initialize an empty list to hold the formatted strings.
        docs = []
        # Iterate over the parts and prepend a "-" to each, except for the first one if it's empty.
        for part in parts:
            # Strip leading and trailing whitespace for cleaner results.
            trimmed_part = part.strip()
            # If the part is not empty, prepend the "-" and add to the list.
            if trimmed_part:
                docs.append(f"- {trimmed_part}")
        
        return docs
    def split_string_and_extract_columns(self,string):
    # Split the string at each occurrence of the "-" character.
        parts = string.split('-')
        
        # Initialize an empty list to hold the formatted strings.
        docs = []
        # Initialize an empty list to hold the column names.
        column_names = []
        
        # Regular expression pattern to find column names.
        pattern = r"'(.*?)'"
        
        # Iterate over the parts and prepend a "-" to each, except for the first one if it's empty.
        for part in parts:
            # Strip leading and trailing whitespace for cleaner results.
            trimmed_part = part.strip()
            
            # If the part is not empty, prepend the "-" and add to the list.
            if trimmed_part:
                formatted_part = f"- {trimmed_part}"
                docs.append(formatted_part)
                
                # Use regular expression to find the column name.
                match = re.search(pattern, trimmed_part)
                if match:
                    # Add the found column name to the list.
                    column_names.append(match.group(1))
        
        return docs, column_names
    def add_columns(self):
        cols = []
        print(len(self.docs))
        for i in self.docs:
            d, c = self.split_string_and_extract_columns(i)
            print(c)
            cols.append(c[0])
        return cols

    def add_init(self):
        self.collection.add(documents = self.docs, metadatas = self.metadata, ids = self.ids)


    def retrieve(self, query, num=12):
        sp_cols_complete = """"""
        output = self.default
        sp_cols_used = []
        for p in self.cols:
            if p in query:
                sp_cols_used.append(p)
                sp_cols = self.collection.get(where={"columns": p})
                for a in sp_cols["documents"]:
                    sp_cols_complete += f"\n{a}"
        if len(sp_cols_used) > 0:

            result = self.collection.query(query_texts = [query], n_results = num, where={"columns": {"$nin": sp_cols_used}})
        else:
            result = self.collection.query(query_texts = [query], n_results = num)
        
        output += sp_cols_complete
        for i in result["documents"][0]:
            output += f"\n{i}"
        return output
    
    def add_new(self, description):
        self.docs.append(description)
        d, c = self.split_string_and_extract_columns(description)
        self.cols.append(c[0])
        self.metadata.append({"columns": c[0]})
        self.ids.append(str(len(self.cols)))
        self.collection.add(documents = [self.docs[-1]], metadatas = [self.metadata[-1]], ids = [self.ids[-1]])
    def return_all(self):
        result = self.default
        for i in self.docs:
            result += f"\n{i}"
        return result