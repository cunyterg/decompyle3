from decompyle3.show import maybe_show_tree
from copy import copy
import sys

from xdis.code import iscode
from spark_parser import GenericASTTraversal, GenericASTTraversalPruningException
from decompyle3.scanner import Code
from decompyle3.parsers.treenode import SyntaxTree


class TreeTransform(GenericASTTraversal, object):
    def __init__(self, scanner, parser, build_ast, show_ast=False):
        self.showast = show_ast
        self.build_ast = build_ast
        self.currentclass = None
        self.scanner = scanner
        self.p = parser
        self.hide_internal = False
        self.ast_errors = []
        return

    def str_with_template(self, ast):
        sys.stdout.write(str(ast))

    def preorder(self, node=None):
        """Walk the tree in roughly 'preorder' (a bit of a lie explained below).
        For each node with typestring name *name* if the
        node has a method called n_*name*, call that before walking
        children. If there is no method define, call a
        self.default(node) instead. Subclasses of GenericASTTtraversal
        ill probably want to override this method.

        In typical use a node with children can call "preorder" in any
        order it wants which may skip children or order then in ways
        other than first to last.  In fact, this this happens.  So in
        this sense this function not strictly preorder.
        """
        if node is None:
            node = self.ast

        try:
            name = "n_" + self.typestring(node)
            if hasattr(self, name):
                func = getattr(self, name)
                node = func(node)
            else:
                node = self.default(node)
        except GenericASTTraversalPruningException:
            return

        for i, kid in enumerate(node):
            node[i] = self.preorder(kid)
        return node

    def default(self, node):
        # print(f"node is {node.kind}")
        return node

        # if key.kind in table:
        #     self.template_engine(table[key.kind], node)
        #     self.prune()

    def n_classdef(self, node):
        self.n_classdef3(node)
        return node

    def n_classdef3(self, node):
        # class definition ('class X(A,B,C):')

        # Pick out various needed bits of information
        # * class_name - the name of the class
        # * subclass_info - the parameters to the class  e.g.
        #      class Foo(bar, baz)
        #               ----------
        # * subclass_code - the code for the subclass body
        if node == "classdefdeco2":
            class_name = node[1][1].attr
            build_class = node
        else:
            build_class = node[0]
            if build_class == "build_class_kw":
                mkfunc = build_class[1]
                assert mkfunc == "mkfunc"
                if hasattr(mkfunc[0], "attr") and iscode(mkfunc[0].attr):
                    subclass_code = mkfunc[0].attr
                else:
                    assert mkfunc[0] == "load_closure"
                    subclass_code = mkfunc[1].attr
                    assert iscode(subclass_code)
            if build_class[1][0] == "load_closure":
                code_node = build_class[1][1]
            else:
                code_node = build_class[1][0]
            class_name = code_node.attr.co_name

        assert "mkfunc" == build_class[1]
        self.currentclass = str(class_name)
        return node

    def n_ifstmt(self, node):
        """Here we are just going to check if we can turn an 'ifstmt' into 'assert'"""
        testexpr = node[0]
        ifstmts_jump = node[1]
        if testexpr != "testexpr" or node[1] != "_ifstmts_jump":
            # No dice
            return node
        stmts = ifstmts_jump[0]
        if stmts in ("c_stmts",) and len(stmts) == 1:
            stmt = stmts[0]
            raise_stmt = stmt[0]
            if raise_stmt == "raise_stmt1" and len(testexpr[0]) == 2:
                # ifstmt
                #   0. testexpr (2)
                #      testtrue
                #       0. expr
                #   1. _ifstmts_jump (2)
                #      0. c_stmts
                #        stmts
                #           raise_stmt1 (2)
                #             0. expr
                #                  LOAD_ASSERT
                #             1.   RAISE_VARARGS_1
                # becomes:
                # assert ::= assert_expr jmp_true LOAD_ASSERT RAISE_VARARGS_1 COME_FROM
                assert_expr = testexpr[0][0]
                assert_expr.kind = "assert_expr"
                jmp_true = testexpr[0][1]
                LOAD_ASSERT = raise_stmt[0][0]
                RAISE_VARARGS_1 = raise_stmt[1]
                node = SyntaxTree(
                    "assert", [assert_expr, jmp_true, LOAD_ASSERT, RAISE_VARARGS_1]
                )
                pass
            # elif raise_stmt == "raise_stmt2" ...
            pass
        return node

    def n_mkfunc(self, node):
        code = node[-3]
        code = Code(node[-3].attr, self.scanner, self.currentclass)
        ast = self.build_ast(
            self,
            code._tokens,
            code._customize,
            is_lambda=False,
            noneInNames=("None" in code.co_names),
        )
        self.traverse(ast)
        return node

    def traverse(self, node, is_lambda=False):
        node = self.preorder(node)
        return node

    def transform(self, ast):
        self.ast = copy(ast)
        self.ast = self.traverse(self.ast, is_lambda=False)
        maybe_show_tree(self, self.ast)
        return self.ast

    # Write template_engine
    # def template_engine
