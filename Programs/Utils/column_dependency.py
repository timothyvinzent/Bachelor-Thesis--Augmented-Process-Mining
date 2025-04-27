import networkx as nx


dependencies = {
    "amount": [],
    "org_resource": [],
    "dismissal": [],
    "concept_name": [],
    "vehicleClass": [],
    "totalPaymentAmount": [],
    "lifecycle_transition": [],
    "time_timestamp": [],
    "article": [],
    "points": [],
    "case_concept_name": [],
    "expense": [],
    "notificationType": [],
    "lastSent": [],
    "paymentAmount": [],
    "matricola": [],
    "dismissed_by_prefecture": ["dismissal", "case_concept_name"],
    "dismissed_by_judge": ["dismissal", "case_concept_name"],
    "maxtotalPaymentAmount": ["totalPaymentAmount", "case_concept_name"],
    "duration": ["case_concept_name", "time_timestamp"],
    "event_count": ["case_concept_name"],
    "expense_sum": ["case_concept_name", "expense"],
    "amount_min": ["case_concept_name", "amount"],
    "amount_last": ["case_concept_name", "amount"],
    "dismissed": ["dismissal", "case_concept_name"],
    "credit_collected": ["case_concept_name", "concept_name"],
    "obligation_topay_cancelled": ["case_concept_name", "concept_name", "time_timestamp"],
    "penalty_added": ["case_concept_name", "concept_name"],
    "dismissed_by_other": ["dismissal", "case_concept_name"],
    "appealed_to_judge": ["case_concept_name", "concept_name"],
    "appealed_to_prefecture": ["case_concept_name", "concept_name"],
    "appeal_to_judgeorprefecture": ["case_concept_name", "concept_name"],
    "add_penalty_count": ["case_concept_name", "concept_name"],
    "send_fine_count": ["case_concept_name", "concept_name"],
    "payment_count": ["case_concept_name", "concept_name"],
    "insert_fine_notification_count": ["case_concept_name", "concept_name"],
    "send_for_credit_collection_count": ["case_concept_name", "concept_name"],
    "insert_date_appeal_to_prefecture_count": ["case_concept_name", "concept_name"],
    "send_appeal_to_prefecture_count": ["case_concept_name", "concept_name"],
    "receive_result_appeal_from_prefecture_count": ["case_concept_name", "concept_name"],
    "notify_result_appeal_to_offender_count": ["case_concept_name", "concept_name"],
    "time_timestamp_beginn": ["case_concept_name", "time_timestamp"],
    "time_timestamp_end": ["case_concept_name", "time_timestamp"],
    "appeal_to_judge_count": ["case_concept_name", "concept_name"],
    "outstanding_balance": ["amount_last", "expense_sum", "maxtotalPaymentAmount"],
    "credit_collected_AND_dismissed": ["credit_collected", "dismissed"],
    "paid_nothing": ["maxtotalPaymentAmount"],
    "appeal_judge_cancelled": ["appealed_to_judge", "dismissed_by_judge"],
    "appeal_prefecture_cancelled": ["appealed_to_prefecture", "dismissed_by_prefecture"],
    "fully_paid": ["outstanding_balance"],
    "overpaid": ["outstanding_balance"],
    "underpaid": ["outstanding_balance"],
    "credit_collected_AND_fully_paid": ["fully_paid", "credit_collected"],
    "dismissed_AND_fully_paid": ["dismissed", "fully_paid"],
    "overpaid_amount": ["overpaid", "outstanding_balance"],
    "underpaid_amount": ["underpaid", "outstanding_balance"],
    "part_paid": ["fully_paid", "paid_nothing"],
    "unresolved": ["fully_paid", "credit_collected", "dismissed"],
    "paid_without_obligation": ["obligation_topay_cancelled", "fully_paid"]
}

vanilla_cols = [
    "amount",
    "org_resource",
    "dismissal",
    "concept_name",
    "vehicleClass",
    "totalPaymentAmount",
    "lifecycle_transition",
    "time_timestamp",
    "article",
    "points",
    "case_concept_name",
    "expense",
    "notificationType",
    "lastSent",
    "paymentAmount",
    "matricola",
]



class DependencyGraph:
    def __init__(self, vanilla_cols, col_instructions, dependencies=dependencies):
        self.dependencies = dependencies
        vanilla_cols.append("case_concept_name")
        vanilla_cols.append("time_timestamp")
        self.vanilla_cols = vanilla_cols
        self.graph = self._create_graph()
        self.col_instructions = {}
        self.col_definitions = {}

        for instruction, cols, dep, t in col_instructions.values:
            self.col_instructions[cols] = instruction
            # for the instruction string, remove the string "Create a colum called " or "Create column called "
            str_repl_1 = "Create a column called "
            str_repl_2 = "Create column called "
            if str_repl_1 in instruction:
                col_def = instruction.replace("Create a column called ", "")
            elif str_repl_2 in instruction:
                col_def = instruction.replace("Create column called ", "")

            


            self.col_definitions[cols] = col_def
            

    def _create_graph(self):
        G = nx.DiGraph()
        for column, deps in self.dependencies.items():
            for dep in deps:
                G.add_edge(dep, column)
        return G

    def find_upstream_dependencies(self, columns, available_cols):
        upstream_nodes = set()
        nodes_to_explore = list(columns)
        while nodes_to_explore:
            current_node = nodes_to_explore.pop()
            if current_node in available_cols:
                upstream_nodes.add(current_node)
                continue
            else:
                upstream_nodes.add(current_node)
                parents = list(nx.bfs_edges(self.graph, current_node, depth_limit=1, reverse=True))
                for parent in parents:
                    parent_node = parent[1]
                    if parent_node not in available_cols:
                        nodes_to_explore.append(parent_node)
                    else:
                        upstream_nodes.add(parent_node)
        return self.graph.subgraph(upstream_nodes)

    def cols(self, requested_columns, available_cols= None):
        if available_cols is None:
            available_cols = self.vanilla_cols
        else:
            # check which cols in vanill cols are not present in available cols, add those
            for col in self.vanilla_cols:
                if col not in available_cols:
                    available_cols.append(col)
        subgraph = self.find_upstream_dependencies(requested_columns, available_cols)
        return self.get_columns_to_generate(subgraph, requested_columns, available_cols)

    def get_columns_to_generate(self, subgraph, requested_columns, available_cols):
        try:
            sorted_nodes = list(nx.topological_sort(subgraph))
        except nx.NetworkXUnfeasible:
            raise ValueError("The graph contains a cycle, which is not allowed for topological sorting.")
        
        columns_to_generate = []
        total_generated = available_cols.copy()
        for node in sorted_nodes:
            if node not in available_cols:
                dependencies = list(subgraph.predecessors(node))
                if all(dep in total_generated for dep in dependencies):
                    columns_to_generate.append(node)
                    total_generated.append(node)
                else:
                    print("Not all dependencies are available for node:", node)
        
        if all(column in available_cols for column in requested_columns):
            return None
        
        return columns_to_generate
    
    def instructions_c(self, columns_to_generate):
        instructions = []
        for col in columns_to_generate:
            instructions.append(self.col_instructions[col])
        return instructions
    def definitions_s(self, columns_to_generate):
        definitions = []
        for col in columns_to_generate:
            definitions.append(self.col_definitions[col])
        return definitions
