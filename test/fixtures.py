from thrift.Thrift import TType
from thriftmodel.model import (
        ThriftField, ThriftModel, RecursiveThriftModel, IntField, ListField,
        MapField, StringField, StructField, serialize, deserialize)


class NodeData(ThriftModel):
    name = StringField()
    age = IntField()
    skills = MapField(StringField(), IntField())

class TreeNode(RecursiveThriftModel):
    pass

TreeNode.make_thrift_spec({
        'children': ListField(TreeNode),
        'data': StructField(NodeData)})


data = TreeNode(
        children=[
            TreeNode(
                    children=[TreeNode(data=NodeData(name="ulrik", age=9))],
                    data=NodeData(
                        name="josef",
                        age=33,
                        skills={
                            "guitar": 5,
                            "swimming": 10}),
                ),
            TreeNode(
                data=NodeData(name="julia", age=27)),
            TreeNode(
                    children=[
                        TreeNode(
                            data=NodeData(name="hans", age=91),
                            children=[TreeNode(data=NodeData(name="A"))])
                    ],
                    data=NodeData(name="julio", age=67)
                )
            ]
       )
