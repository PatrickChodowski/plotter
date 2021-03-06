
class SqlBuilder:
    '''
    SQl builder class should receive information about:
        - metrics
        - dimensions
        - table name
        - project
        - schema
        - required fields
        - calculations
        - filters
        - limits
    '''

    def __init__(self, **kwargs):

        self.metrics = kwargs['metrics'].split(';')
        self.dimensions = kwargs['dimensions'].split(';')
        self.source = kwargs['source']
        self.aggr_type = kwargs['aggr_type']

        self.add_filters = kwargs['add_filters']
        self.filters = kwargs['filters']
        self.having = kwargs['having']
        self.show_top_n = kwargs['show_top_n']
        self.data_source = kwargs['data_source']

        self.current_db_source = kwargs['current_db_source']

        self.project = self.current_db_source['project']
        self.file_format = self.current_db_source['file_format']

        self.df_name = None
        self.schema = None
        self.calculations = None
        self.calculations_full = None

        self.req_fields = None
        if 'req_fields' in kwargs.keys():
            self.req_fields = kwargs['req_fields']

    def _no_aggr_select(self, **args):
        select_list = list()
        calc_list = list()
        metric_list = list()

        if (self.dimensions.__len__() > 0) & (self.dimensions != ['']):
            dim_txt = ', '.join(self.dimensions)
            select_list.append(dim_txt)

        if (self.metrics.__len__() > 0) & (self.metrics != ['']):
            for metric in self.metrics:
                if metric in self.calculations:
                    calc_list.append(f" {self.calculations_full[metric]} AS {metric} ")
                else:
                    metric_list.append(metric)

            metrics_txt = ', '.join(metric_list)
            calcs_txt = ', '.join(calc_list)

            select_list.append(metrics_txt)
            select_list.append(calcs_txt)

        # required fields
        if (self.req_fields is not None) & (self.req_fields != ['']):
            select_list.append(self.req_fields)

        where_str = self._gen_where_statements()
        ord_txt = self._gen_order_statement()

        select_list = [txt for txt in select_list if txt != '']
        select_txt = ','.join(select_list)

        sql = f"""SELECT {select_txt} FROM {self.project}.{self.schema}.{self.df_name} 
WHERE 1=1 {where_str} {ord_txt}"""
        return sql

    def _gb_aggr_select(self, **args):
        select_list = list()
        calc_list = list()
        metric_list = list()
        gb_txt = ''
        metric_queries = list()
        hv_txt = ''

        aggr_type = self.aggr_type + '('
        if self.aggr_type == 'count_unique':
            aggr_type = ' COUNT(DISTINCT '

        if (self.dimensions.__len__() > 0) & (self.dimensions != ['']):
            dim_txt = ', '.join(self.dimensions)
            select_list.append(dim_txt)
            gb_txt = f'GROUP BY {dim_txt}'
            hv_txt = self._gen_having_statement(gb_txt)

        for metric in self.metrics:
            if metric not in self.calculations:
                metric_queries.append(f"{aggr_type.replace('ntile_','')}{metric}) AS {metric}")
            else:
                calc_list.append(f" {self.calculations_full[metric]} AS {metric} ")

        metrics_txt = ','.join(metric_queries)
        select_list.append(metrics_txt)

        calcs_txt = ', '.join(calc_list)
        select_list.append(calcs_txt)

        select_list = [txt for txt in select_list if txt != '']
        select_txt = ','.join(select_list)

        where_str = self._gen_where_statements()
        ord_txt = self._gen_order_statement()
        sql = f"""SELECT {select_txt} FROM {self.project}.{self.schema}.{self.df_name} 
WHERE 1=1 {where_str} {gb_txt} {hv_txt} {ord_txt}"""

        return sql

    def _quantiles_aggr_select(self, **args):
        select_list = list()
        gb_txt = ' OVER () '
        metric_queries = list()
        if (self.dimensions.__len__() > 0) & (self.dimensions != ['']):
            dim_txt = ', '.join(self.dimensions)
            select_list.append(dim_txt)
            gb_txt = f' OVER(PARTITION BY {dim_txt}) '

        q_options = [0.10, 0.25, 0.50, 0.75, 0.90]
        for qopt in q_options:
            for nc in self.metrics:
                if nc not in self.calculations:
                    metric_queries.append(f"PERCENTILE_CONT({nc}, {qopt}) {gb_txt} AS q{str(qopt).replace('.','')}_{nc}")

        metrics_txt = ','.join(metric_queries)
        select_list.append(metrics_txt)
        select_txt = ','.join(select_list)

        where_str = self._gen_where_statements()
        ord_txt = self._gen_order_statement()
        sql = f"""SELECT DISTINCT {select_txt} FROM {self.project}.{self.schema}.{self.df_name} 
        WHERE 1=1 {where_str} """

        return sql

    def _ntile_aggr_select(self, **args):
        select_list = list()
        gb_txt = 'OVER( '
        metric_queries = list()

        if (self.dimensions.__len__() > 0) & (self.dimensions != ['']):
            dim_txt = ', '.join(self.dimensions)
            select_list.append(dim_txt)
            gb_txt = f' OVER(PARTITION BY {dim_txt}  '

        for nc in self.metrics:
            if nc not in self.calculations:
                metric_queries.append(f"NTILE(100) {gb_txt} ORDER BY {nc} DESC) AS ntile_{nc}")

        metrics_txt = ','.join(metric_queries)
        select_list.append(metrics_txt)
        select_txt = ','.join(select_list)

        where_str = self._gen_where_statements()

        sql = f"""SELECT {select_txt} FROM {self.project}.{self.schema}.{self.df_name} 
               WHERE 1=1 {where_str} """

        return sql

    def _ntile_over_aggr_select(self, **args):
        #'ntile_avg' 'ntile_sum' 'ntile_min' 'ntile_max'
        select_list = list()
        metric_queries = list()
        # thats basically a first subquery to get average per dimension:

        if (self.dimensions.__len__() > 0) & (self.dimensions != ['']):
            dim_txt = ', '.join(self.dimensions)
            select_list.append(dim_txt)

        for nc in self.metrics:
            metric_queries.append(f"NTILE(100) OVER ( ORDER BY {nc} DESC ) AS ntile_{nc}")

        metrics_txt = ','.join(metric_queries)
        select_list.append(metrics_txt)
        select_txt = ','.join(select_list)

        sql0 = self._gb_aggr_select()

        sql = f"""SELECT {select_txt}
FROM ({sql0}) a"""


        return sql


    def make_query(self, **args):
        # read table name
        try:
            self.df_name = self.data_source[self.source]['table']
            self.schema = self.data_source[self.source]['schema']

            # calculations
            if self.check_key(self.data_source[self.source], 'calculations'):
                possible_calcs = self.data_source[self.source]['calculations']
                calcs_dict = dict((key, d[key]) for d in possible_calcs for key in d)
                self.calculations = list(calcs_dict.keys())
                self.calculations_full = calcs_dict

            #  when there is un-aggregated metric and aggregated calc
            if (any(m in self.calculations for m in self.metrics)) & (self.aggr_type == '') & (any(m not in self.calculations for m in self.metrics)):
                raise Exception('IF there is a metric and calculation, there has to be nonempty aggregation selected')

            sql_switch = {'':   self._no_aggr_select,
                          'sum': self._gb_aggr_select,
                          'max': self._gb_aggr_select,
                          'min': self._gb_aggr_select,
                          'avg': self._gb_aggr_select,
                          'count': self._gb_aggr_select,
                          'count_unique': self._gb_aggr_select,
                          'quantiles': self._quantiles_aggr_select,
                          'ntile': self._ntile_aggr_select,
                          'ntile_avg': self._ntile_over_aggr_select,
                          'ntile_sum': self._ntile_over_aggr_select,
                          'ntile_min': self._ntile_over_aggr_select,
                          'ntile_max': self._ntile_over_aggr_select}
            sql = sql_switch[self.aggr_type](**args)
            return sql
        except Exception as e:
            raise



    def _gen_where_statements(self):
        where_str = ''
        for k, v in self.filters.items():
            if k in self.add_filters:
                if ';' in v:
                    v2 = "('" + v.replace(";", "','") + "')"
                    wstr = f" AND CAST({k} AS STRING) IN {v2} "
                else:
                    wstr = f" AND CAST({k} AS STRING) = '{v}' "
                where_str += wstr
            else:
                pass
        return where_str

    def _gen_having_statement(self, gb_txt):
        hv_txt = ''
        if (gb_txt != '') & (self.having != ''):
            hv_txt = f'HAVING {self.having} '
        return hv_txt

    def _gen_order_statement(self):
        ord_txt = ''
        if (self.metrics.__len__() > 0) & (int(self.show_top_n) > 0):
            ord_txt = f" ORDER BY {self.metrics[0]} DESC LIMIT {self.show_top_n} "
        return ord_txt

    @staticmethod
    def check_key(dict, key):
        if key in dict.keys():
            return True
        else:
            return False