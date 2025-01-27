from __future__ import annotations
import os
import Def
from typing import Optional
from typing import List
from typing import Tuple
from os.path import exists
from Lexer import Token
from Lexer import TokenKind
from Lexer import tokenize
from Lexer import token_is_lit
from Lexer import token_is_param
from Lexer import token_is_op
from Lexer import token_is_paren
from Lexer import post_process
from Lexer import token_is_bin_op
from Lexer import token_is_unary_op
from Lexer import token_is_rassoc
from Def import Node
from Def import NodeKind
from Def import Variable
from Def import VariableCompKind
from Def import VariableType
from Def import VariableKind
from Def import VariableMetaKind
from Def import Function
from Def import FunctionSignature
from Def import Array
from Def import Structure
from Def import Pointer
from Def import Macro
from Def import MacroSignature
from Def import bool_ckind
from Def import ptr_ckind
from Def import ref_ckind
from Def import arr_ckind
from Def import void_ckind
from Def import default_ckind
from Def import struct_ckind
from Def import any_type
from Def import void_type
from Def import bool_type
from Def import default_type
from Def import str_type
from Def import print_error
from Def import check_ident
from Def import type_of
from Def import type_of_op
from Def import type_of_ident
from Def import type_of_lit
from Def import type_compatible
from Def import full_name_of_var
from Def import full_name_of_fun
from Def import needs_widen
from Def import type_of_cast
from Def import allowed_op
from Def import size_of
from Def import is_local_ident
from Def import rev_type_of
from Def import node_is_cmp
from Def import check_signature
from Def import _find_signature
from Def import glue_statements
from Snippet import copy_of

PRECEDENCE_MAP = {
    TokenKind.KW_CAST: 26,
    TokenKind.KW_TYPE: 26,
    TokenKind.KW_LEN: 26,
    TokenKind.KW_SIZE: 26,
    TokenKind.KW_COUNT: 26,
    TokenKind.KW_LIT: 26,
    TokenKind.DEREF: 26,
    TokenKind.AMP: 26,
    TokenKind.KW_ASM: 25,
    TokenKind.FUN_CALL: 25,
    TokenKind.MACRO_CALL: 26,
    TokenKind.PERIOD: 24,
    TokenKind.PLUS: 10,
    TokenKind.MINUS: 10,
    TokenKind.MULT: 20,
    TokenKind.DIV: 20,
    TokenKind.PERC: 7,
    TokenKind.BIT_OR: 7,
    TokenKind.BIT_AND: 7,
    TokenKind.OR: 5,
    TokenKind.AND: 5,
    TokenKind.KW_AT: 27,
    TokenKind.KW_IF: 4,
    TokenKind.KW_ELSE: 4,
    TokenKind.ASSIGN: 3,
    TokenKind.EQ: 6,
    TokenKind.NEQ: 6,
    TokenKind.GT: 6,
    TokenKind.LT: 6,
    TokenKind.LTE: 6,
    TokenKind.GTE: 6,
    TokenKind.COMMA: 2,
}

NODE_KIND_MAP = {
    TokenKind.INT_LIT: NodeKind.INT_LIT,
    TokenKind.CHAR_LIT: NodeKind.CHAR_LIT,
    TokenKind.PLUS: NodeKind.OP_ADD,
    TokenKind.MINUS: NodeKind.OP_SUB,
    TokenKind.MULT: NodeKind.OP_MULT,
    TokenKind.DIV: NodeKind.OP_DIV,
    TokenKind.PERC: NodeKind.OP_MOD,
    TokenKind.OR: NodeKind.OP_OR,
    TokenKind.AND: NodeKind.OP_AND,
    TokenKind.BIT_OR: NodeKind.OP_BIT_OR,
    TokenKind.BIT_AND: NodeKind.OP_BIT_AND,
    TokenKind.ASSIGN: NodeKind.OP_ASSIGN,
    TokenKind.EQ: NodeKind.OP_EQ,
    TokenKind.NEQ: NodeKind.OP_NEQ,
    TokenKind.LT: NodeKind.OP_LT,
    TokenKind.GT: NodeKind.OP_GT,
    TokenKind.LTE: NodeKind.OP_LTE,
    TokenKind.GTE: NodeKind.OP_GTE,
    TokenKind.IDENT: NodeKind.IDENT,
    TokenKind.COMMA: NodeKind.GLUE,
    TokenKind.KW_AT: NodeKind.ARR_ACC,
    TokenKind.PERIOD: NodeKind.ELEM_ACC,
    TokenKind.DEREF: NodeKind.DEREF,
    TokenKind.AMP: NodeKind.REF,
    TokenKind.FUN_CALL: NodeKind.FUN_CALL,
    TokenKind.STR_LIT: NodeKind.STR_LIT,
    TokenKind.KW_ASM: NodeKind.ASM,
    TokenKind.KW_CAST: NodeKind.CAST,
    TokenKind.KW_TYPE: NodeKind.TYPE,
    TokenKind.KW_LEN: NodeKind.LEN,
    TokenKind.KW_SIZE: NodeKind.SIZE,
    TokenKind.KW_COUNT: NodeKind.COUNT,
    TokenKind.KW_LIT: NodeKind.LIT,
    TokenKind.TRUE_LIT: NodeKind.TRUE_LIT,
    TokenKind.FALSE_LIT: NodeKind.FALSE_LIT,
    TokenKind.KW_IF: NodeKind.TERN_COND,
    TokenKind.KW_ELSE: NodeKind.TERN_BODY,
}


class Parser:
    def __init__(self, parser: Parser = None) -> None:
        if parser is not None:
            self.source = parser.source
            self.lineno = parser.lineno
            self.tokens = list(parser.tokens)
            self.tokens_idx = parser.tokens_idx
            self.lines = list(parser.lines)
            self.lines_idx = parser.lines_idx
        else:
            self.source = ''
            self.lineno = 0
            self.tokens = []
            self.tokens_idx = 0
            self.lines = []
            self.lines_idx = 0

    def parse(self, source: str = '') -> Node:
        if source != '':
            self.source = source
            self.lines = open(source, 'r').readlines()
        self.skip_blank_lines()

        self.tokens = tokenize(self.curr_line())
        return self.program_statement()

    def no_more_lines(self, check_next_lines: bool = False) -> bool:
        return self.lines_idx + (
            1 if check_next_lines else 0) >= len(self.lines)

    def curr_line(self) -> str:
        return self.lines[self.lines_idx]

    def skip_blank_lines(self) -> None:
        while self.curr_line().lstrip('\t ') == '\n' or self.curr_line().lstrip('\t ').startswith('#'):
            self.next_line()

    def next_line(self) -> str:
        self.lineno += 1
        self.lines_idx += 1

        if self.no_more_lines():
            print_error('next_line', 'No more lines in list', self)
        self.skip_blank_lines()

        self.tokens_idx = 0
        self.tokens = tokenize(self.curr_line())
        return self.curr_line()

    def no_more_tokens(self) -> bool:
        return self.tokens_idx >= len(self.tokens)

    def lookahead_token(self) -> Token:
        return self.tokens[self.tokens_idx + 1]

    def curr_token(self) -> Optional[Token]:
        if self.no_more_tokens():
            self.next_line()
            # print_error('curr_token', 'No more tokens in list.', self)

        return self.tokens[self.tokens_idx]

    def next_token(self) -> None:
        self.tokens_idx += 1

    def match_token(self, kind: TokenKind) -> Token:
        # if self.no_more_tokens():
        #     print_error('self.match_token',
        #                 f'Expected token kind {kind}, got nothing', self)
        token = self.curr_token()

        if token.kind != kind:
            print_error('self.match_token',
                        f'Expected token kind {kind}, got {token.kind}', self)

        self.next_token()
        return token

    def match_token_from(self, kinds: Tuple[TokenKind]) -> Token:
        token = self.curr_token()

        if token.kind not in kinds:
            print_error('self.match_token_from',
                        f'Expected token kinds {kinds}, got {token.kind}', self)

        self.next_token()
        return token

    def token_list_to_tree(self) -> Node:
        def curr_expr():
            return self.tokens[self.tokens_idx:]

        token_list = curr_expr()
        while token_list.count(Token(TokenKind.LPAREN, '(')) > token_list.count(Token(TokenKind.RPAREN, ')')) or (
                token_list.count(Token(TokenKind.LBRACE, '[')) > token_list.count(Token(TokenKind.RBRACE, ']'))):
            self.next_line()
            token_list += curr_expr()

        return self.to_tree(self.to_postfix(post_process(token_list)))

    def node_kind_of(self, kind: TokenKind) -> NodeKind:
        if kind not in NODE_KIND_MAP:
            print_error('node_kind_of', f'Invalid token {kind}', self)

        return NODE_KIND_MAP.get(kind)

    def precedence_of(self, kind: TokenKind) -> int:
        if kind not in PRECEDENCE_MAP:
            print_error('precedence_of',
                        f'Expected operator, got {kind}', self)

        return PRECEDENCE_MAP.get(kind)

    def to_postfix(self, tokens: List[Token]) -> List[Token]:
        op_stack = []
        postfix_tokens = []
        prev_token = None

        def cmp_precedence(t: Token, t2: Token):
            return self.precedence_of(t.kind) <= self.precedence_of(t2.kind)

        for token in tokens:
            if token_is_param(token.kind):
                if token_is_lit(token.kind):
                    if Def.ident_map.get(token.value) == VariableMetaKind.ALIAS:
                        name = Def.alias_map.get(token.value)
                        postfix_tokens.append(Token(TokenKind.IDENT, name))
                    else:
                        postfix_tokens.append(token)
                else:
                    # Detects if the token is a function/macro call (token correction)
                    fun_name = full_name_of_fun(token.value)

                    if Def.ident_map.get(fun_name) == VariableMetaKind.ALIAS:
                        fun_name = Def.alias_map.get(fun_name)

                    if Def.ident_map.get(fun_name) == VariableMetaKind.MACRO:
                        op_stack.append(Token(TokenKind.MACRO_CALL, fun_name))

                    elif Def.ident_map.get(fun_name) == VariableMetaKind.FUN:
                        op_stack.append(Token(TokenKind.FUN_CALL, fun_name))

                    else:
                        if prev_token is not None and prev_token.kind == TokenKind.PERIOD:
                            postfix_tokens.append(
                                Token(TokenKind.IDENT, token.value))

                        else:
                            name = full_name_of_var(
                                token.value, exhaustive_match=True)
                            if name not in Def.ident_map and (prev_token is None or prev_token.kind != TokenKind.PERIOD):
                                print_error('to_postfix',
                                            f'Invalid identifier {name}', self)

                            postfix_tokens.append(
                                Token(TokenKind.IDENT, name))

            elif token_is_paren(token.kind):
                if token.kind == TokenKind.LPAREN:
                    op_stack.append(token)

                if token.kind == TokenKind.RPAREN:
                    while len(op_stack) > 0 and op_stack[-1].kind != TokenKind.LPAREN:
                        postfix_tokens.append(op_stack.pop())
                    op_stack.pop()

            elif token_is_op(token.kind):
                # Assembly, type, offset, size, len, cast builtin pass-trough
                if token.kind in (TokenKind.KW_ASM, TokenKind.KW_TYPE, TokenKind.KW_SIZE, TokenKind.KW_COUNT, TokenKind.KW_LEN, TokenKind.KW_LIT, TokenKind.KW_CAST):
                    op_stack.append(token)
                    continue

                # Handles Unary operator (token correction)
                op_token = token
                if prev_token is None or token_is_op(prev_token.kind) or prev_token.kind == TokenKind.LPAREN:
                    if token.kind == TokenKind.MULT:
                        op_token = Token(TokenKind.DEREF, '*')
                    elif token.kind == TokenKind.BIT_AND:
                        op_token = Token(TokenKind.AMP, '&')
                    else:
                        print_error('to_postfix',
                                    f'Invalid unary operator kind {token.kind}', self)

                while len(op_stack) > 0 and (not token_is_rassoc(op_stack[-1].kind)) and op_stack[-1].kind != TokenKind.LPAREN and cmp_precedence(op_token, op_stack[-1]):
                    postfix_tokens.append(op_stack.pop())
                op_stack.append(op_token)

            else:
                print_error('to_postfix',
                            f'Invalid token kind {token.kind}', self)

            prev_token = token

        while len(op_stack) > 0:
            postfix_tokens.append(op_stack.pop())

        return postfix_tokens

    def cast_builtin(self, node: Node) -> Node:
        glue_node = node
        if node.left.kind != NodeKind.GLUE:
            print_error('cast_builtin',
                        'The cast builtin expects exactly 2 arguments, only one was provided', self)

        arg_cnt = 0
        args: list[Node] = []
        while glue_node is not None:
            arg_cnt += 1
            args.append(glue_node.right)
            glue_node = glue_node.left

        if arg_cnt != 2:
            print_error('cast_builtin',
                        f'The cast builtin expects exactly 2 parameters, {arg_cnt} were provided', self)

        str_node = args.pop()
        target_node = args.pop()

        if str_node is None or str_node.kind != NodeKind.STR_LIT:
            print_error('cast_builtin',
                        f'The first argument passed to the cast builtin is not a string literal, got {str_node.kind}', self)

        type_str = str_node.value.lstrip('\"').rstrip('\"')
        return Node(NodeKind.CAST, type_of_cast(type_str), 'cast', target_node)

    def fun_arg_cnt(self, node: Node) -> int:
        arg_cnt = 0
        while node is not None and node.kind == NodeKind.GLUE:
            arg_cnt += 1
            node = node.left
        return arg_cnt

    def args_to_list(self, node: Node, arg_cnt: int) -> List[Node]:
        if node is None:
            return []

        glue_node = node
        arg_list: list[Node] = []
        if glue_node.kind != NodeKind.GLUE:
            arg_list.append(glue_node)
        else:
            cnt = 0
            while glue_node is not None:
                cnt += 1
                glue_node = glue_node.left

            glue_node = node
            if cnt > arg_cnt:
                block_node: Node = copy_of(node)
                arg_list.append(block_node)

                for _ in range(cnt - arg_cnt):
                    block_node = block_node.left
                block_node.left = None

                for _ in range(cnt - arg_cnt + 1):
                    glue_node = glue_node.left

            while glue_node is not None:
                arg_list.append(glue_node.right)
                glue_node = glue_node.left

            arg_list.reverse()

        return arg_list

    def merge_fun_call(self, node: Node) -> Optional[Node]:
        def append_arg(arg_node: Node, left: Node) -> Node:
            new_node: Node = copy_of(arg_node)
            glue_node = new_node
            prev_node = new_node
            while glue_node is not None:
                prev_node = glue_node
                glue_node = glue_node.left

            if left is not None:
                prev_node.left = left

            return new_node

        if node is None:
            return None

        if node.kind != NodeKind.GLUE:
            return node

        left, right = list(
            map(lambda n: self.merge_fun_call(n), (node.left, node.right)))

        if right.kind == NodeKind.GLUE:
            arg_node = append_arg(right, left)
            return (Node(node.kind, node.ntype, node.value, arg_node.left, arg_node.right))
        else:
            return Node(node.kind, node.ntype, node.value, left, right)

    def expand_macro(self, macro: Macro, node: Optional[Node]) -> Optional[Node]:
        if Def.macro_name != '':
            return Node(NodeKind.IDENT, any_type, Def.macro_name)

        #! BUG: Macro definitions with same name must have ascending argument counts
        #! BUG: Due to assigning `signature = macro.signatures[0]`
        arg_cnt = self.fun_arg_cnt(node)
        signature = min(macro.signatures, key=lambda s: s.arg_cnt)
        for sig in macro.signatures:
            if sig.arg_cnt <= arg_cnt and sig.arg_cnt > signature.arg_cnt:
                signature = sig

        arg_list = self.args_to_list(node, signature.arg_cnt)
        arg_names = signature.arg_names

        if len(arg_list) != len(arg_names):
            print_error('expand_macro',
                        f'Macro {macro.name} accepts {len(arg_names)} arguments, but {len(arg_list)} were provided', self)

        arg_names = list(
            map(lambda name: full_name_of_var(name, exhaustive_match=False), arg_names))
        for name in arg_names:
            check_ident(name)
            Def.ident_map[name] = VariableMetaKind.ANY

        # Add to Def.macro_arg_map
        for name, node in zip(arg_names, arg_list):
            Def.macro_arg_map[name] = node

        def expand_helper(node: Node) -> Optional[Node]:
            if node is None:
                return None

            middle, left, right = list(
                map(lambda n: expand_helper(n), (node.middle, node.left, node.right)))

            return Node(node.kind, node.ntype, node.value, left, right, middle)

        parser = Parser(signature.parser)
        parser.source = self.source
        parser.lineno = self.lineno - 1
        try:
            body = parser.compound_statement()
        except RecursionError:
            print_error('expand_macro',
                        f'Cannot expand macro {macro.name} (circular macro)', self)
        self.lineno += (parser.lineno - self.lineno)

        # Defer fix
        Def.deferred = expand_helper(Def.deferred)

        # Removes macro placeholders
        for name in arg_names:
            if Def.ident_map.get(name) == VariableMetaKind.ANY:
                del Def.ident_map[name]
                del Def.macro_arg_map[name]
        return expand_helper(body)

    def _fun_call(self, fun_name: str, node_stack: List[Node]) -> List[Node]:
        if fun_name in Def.fun_sig_map:
            fun_name = Def.fun_sig_map.get(fun_name)

        fun = Def.fun_map.get(fun_name)
        kind = NodeKind.FUN_CALL

        if fun.arg_cnt == 0 and not fun.is_variadic:
            node_stack.append(Node(kind, fun.ret_type, fun_name))
        else:
            if len(node_stack) == 0:
                print_error('to_tree',
                            f'Missing function operand of {fun_name}', self)

            node = self.merge_fun_call(node_stack.pop()) if len(
                node_stack) > 0 else None
            node_stack.append(
                Node(kind, fun.ret_type, fun_name, node))

        return node_stack

    def to_tree(self, tokens: List[Token]) -> Node:
        node_stack: list[Node] = []

        for token in tokens:
            if token_is_param(token.kind):
                # Lineno builtin
                if token.kind == TokenKind.KW_LINENO:
                    node_stack.append(
                        Node(NodeKind.INT_LIT, type_of_lit(NodeKind.INT_LIT), str(self.lineno + 1)))

                # Line builtin
                elif token.kind == TokenKind.KW_LINE:
                    chars = '\t '
                    newline = '\n'
                    node_stack.append(
                        Node(NodeKind.STR_LIT, type_of_lit(NodeKind.STR_LIT), f'"{self.curr_line().lstrip(chars).rstrip(newline)}"'))

                # Fun builtin
                elif token.kind == TokenKind.KW_FUN:
                    node_stack.append(
                        Node(NodeKind.STR_LIT, type_of_lit(NodeKind.STR_LIT), f'"{Def.fun_name}"'))

                # Macro builtin
                elif token.kind == TokenKind.KW_MACRO:
                    node_stack.append(
                        Node(NodeKind.STR_LIT, type_of_lit(NodeKind.STR_LIT), f'"{Def.macro_name}"'))

                # File builtin
                elif token.kind == TokenKind.KW_FILE:
                    node_stack.append(
                        Node(NodeKind.STR_LIT, type_of_lit(NodeKind.STR_LIT), f'"{self.source}"'))

                # Distinguishes between identifiers and literals
                elif token.kind == TokenKind.IDENT:
                    name = token.value
                    if Def.macro_name == '' and Def.ident_map.get(name) == VariableMetaKind.ANY:
                        if name not in Def.macro_arg_map:
                            node_stack.append(
                                Node(self.node_kind_of(token.kind), any_type, token.value))
                        else:
                            node_stack.append(
                                Def.macro_arg_map.get(token.value))

                    else:
                        name = token.value
                        ntype = type_of_ident(name)
                        if Def.ident_map.get(name) == VariableMetaKind.REF:
                            ntype = Def.ptr_map.get(name).elem_type

                        node_stack.append(
                            Node(self.node_kind_of(token.kind), ntype, name))

                else:
                    kind = self.node_kind_of(token.kind)
                    node_stack.append(
                        Node(kind, type_of_lit(kind), token.value))

            if token_is_op(token.kind):
                if token_is_unary_op(token.kind):
                    # Function call fix
                    if token.kind == TokenKind.FUN_CALL:
                        self._fun_call(token.value, node_stack)
                        # fun_name = token.value
                        # if fun_name in Def.fun_sig_map:
                        #     fun_name = Def.fun_sig_map.get(fun_name)

                        # fun = Def.fun_map.get(fun_name)
                        # kind = self.node_kind_of(token.kind)

                        # if fun.arg_cnt == 0 and not fun.is_variadic:
                        #     node_stack.append(
                        #         Node(kind, fun.ret_type, token.value))
                        # else:
                        #     if len(node_stack) == 0:
                        #         print_error('to_tree',
                        #                     f'Missing function operand of {token.value}', self)
                        #     node = self.merge_fun_call(node_stack.pop()) if len(
                        #         node_stack) > 0 else None
                        #     node_stack.append(
                        #         Node(kind, fun.ret_type, token.value, node))
                        continue

                    if token.kind == TokenKind.MACRO_CALL:
                        macro = Def.macro_map.get(token.value)

                        if macro.arg_cnt == 0:
                            node_stack.append(self.expand_macro(macro, None))
                        else:
                            if len(node_stack) == 0:
                                print_error('to_tree',
                                            'Missing macro operand', self)

                            node = node_stack.pop()
                            body = self.expand_macro(
                                macro, node)

                            node_stack.append(body)

                        continue

                    if len(node_stack) == 0:
                        print_error('to_tree', 'Missing operand', self)
                    node = node_stack.pop()

                    if token.kind == TokenKind.KW_LIT:
                        node_stack.append(Node(self.node_kind_of(
                            token.kind), void_type, token.value, node))
                        continue

                    if token.kind == TokenKind.KW_TYPE:
                        node_stack.append(
                            Node(self.node_kind_of(token.kind), type_of_lit(NodeKind.STR_LIT), token.value, node))
                        continue

                    if token.kind in (TokenKind.KW_LEN, TokenKind.KW_SIZE, TokenKind.KW_COUNT):
                        node_stack.append(
                            Node(self.node_kind_of(token.kind), type_of_lit(NodeKind.INT_LIT), token.value, node))
                        continue

                    # Cast builtin
                    if token.kind == TokenKind.KW_CAST:
                        node_stack.append(self.cast_builtin(node))
                        continue

                    kind = self.node_kind_of(token.kind)
                    if kind not in (NodeKind.ASM, NodeKind.FUN_CALL) and kind not in allowed_op(node.ntype.ckind):
                        print_error(
                            'to_tree', f'Incompatible type {rev_type_of(node.ntype)}', self)

                    op_type = type_of_op(kind, node.ntype)
                    if kind == NodeKind.DEREF and op_type == void_type:
                        print_error('to_tree',
                                    f'Cannot dereference the {node.value} pointer-to-void', self)

                    if kind == NodeKind.REF and node.kind != NodeKind.IDENT:
                        print_error('to_tree',
                                    f'Can only reference identifiers, got {node.kind}', self)

                    node_stack.append(
                        Node(kind, type_of_op(kind, node.ntype), token.value, node))

                elif token_is_bin_op(token.kind):
                    if len(node_stack) < 2:
                        # ? Dirty fix
                        if token.kind == TokenKind.PERIOD:
                            continue

                        print_error(
                            'to_tree', f'Missing operand {token.kind} {node_stack[0]}', self)

                    right = node_stack.pop()
                    left = node_stack.pop()

                    # Validates array/pointer acesses
                    if token.kind == TokenKind.KW_AT and left.ntype != any_type:
                        elem_cnt = 0
                        if Def.ident_map.get(left.value) == VariableMetaKind.PTR:
                            elem_cnt = Def.ptr_map.get(left.value).elem_cnt
                        elif Def.ident_map.get(left.value) == VariableMetaKind.ARR:
                            elem_cnt = Def.arr_map.get(left.value).elem_cnt
                        else:
                            print_error('to_tree',
                                        f'Expected a pointer/array identifier, got {left.value}', self)

                        # Validates fixed-index array acesses
                        if right.kind == NodeKind.INT_LIT:
                            idx = int(right.value)
                            if elem_cnt > 0 and idx >= elem_cnt:
                                print_error('to_tree',
                                            f'Cannot access element at {idx} from {left.value}', self)

                    # Creates the initial parameter tree of a function call
                    if token.kind == TokenKind.COMMA and left.kind != NodeKind.GLUE:
                        node_stack.append(Node(NodeKind.GLUE, void_type, '', Node(
                            NodeKind.GLUE, void_type, '', None, left), right))

                    else:
                        kind = self.node_kind_of(token.kind)

                        # De-sugars a member-like function call
                        if kind == NodeKind.ELEM_ACC and Def.ident_map.get(left.value) == VariableMetaKind.NAMESPACE:
                            name = f'{left.value}_{right.value}'

                            if Def.ident_map.get(name) == VariableMetaKind.FUN:
                                self._fun_call(name, node_stack)
                            else:
                                ntype = type_of_ident(name)
                                node_stack.append(
                                    Node(NodeKind.IDENT, ntype, f'{left.value}_{right.value}'))
                            continue

                        # Builds the python-like ternary condition (check #1)
                        if kind != NodeKind.TERN_BODY and left.kind == NodeKind.TERN_COND:
                            print_error('to_tree',
                                        'Missing else clause in ternary condition', parser=self)
                        if kind == NodeKind.TERN_BODY:
                            if left.kind != NodeKind.TERN_COND:
                                print_error('to_tree',
                                            f'Expected a ternary condition, got {left.kind}', parser=self)

                            if not type_compatible(NodeKind.FUN_CALL, right.ntype.ckind, left.left.ntype.ckind):
                                print_error('to_tree',
                                            f'Incompatible types in ternary condition {kind} {rev_type_of(left.ntype)}, {rev_type_of(right.ntype)}', parser=self)

                            node_stack.append(
                                Node(NodeKind.TERN, right.ntype, '', left.left, right, left.right))
                            continue

                        if kind == NodeKind.ELEM_ACC and right.kind == NodeKind.FUN_CALL:
                            args = Node(NodeKind.GLUE, void_type, '', Node(
                                NodeKind.GLUE, void_type, '', None, left), right.left)
                            new_args = self.merge_fun_call(args)
                            node_stack.append(
                                Node(right.kind, right.ntype, right.value, new_args))
                            continue

                        if left.kind != NodeKind.GLUE and kind != NodeKind.GLUE and (left.ntype == void_type or right.ntype == void_type or not type_compatible(kind, left.ntype.ckind, right.ntype.ckind)):
                            print_error('to_tree',
                                        f'to_tree: Incompatible types {kind} {rev_type_of(left.ntype)}, {rev_type_of(right.ntype)} (check #1)', self)

                        if kind not in allowed_op(left.ntype.ckind):
                            print_error('to_tree',
                                        f'to_tree: Incompatible types {kind} {rev_type_of(left.ntype)}, {rev_type_of(right.ntype)} (check #2)', self)

                        # Widens the operands if necessary
                        code = needs_widen(left.ntype.ckind, right.ntype.ckind)
                        if code == 1 and kind not in (NodeKind.GLUE, NodeKind.OP_ASSIGN, NodeKind.TERN_COND):
                            left = Node(NodeKind.OP_WIDEN,
                                        right.ntype, left.value, left)
                        if code == 2 and kind not in (NodeKind.GLUE, NodeKind.TERN_COND):
                            right = Node(NodeKind.OP_WIDEN, left.ntype,
                                         right.value, right)

                        node_stack.append(
                            Node(kind, type_of_op(kind, left.ntype), token.value, left, right))
                else:
                    print_error('to_tree',
                                f'Operator kind {token.kind} is neither binary or unary', self)

        if len(node_stack) > 1:
            def val_of(node: Node) -> str:
                return node.value

            print_error('to_tree',
                        f'Unused operands [{", ".join(map(val_of, node_stack[1:]))}]', self)

        if len(node_stack) == 0:
            print_error('to_tree',
                        'Missing operands (attempt to pop from empty list)', self)

        node = node_stack.pop()
        if node.kind in (NodeKind.TERN_COND, NodeKind.TERN_BODY):
            print_error('to_tree',
                        'Missing else clause in ternary condition', parser=self)

        return node

    def statement(self) -> Optional[Node]:
        token = self.curr_token()
        if token.kind == TokenKind.KW_LET:
            self.next_token()
            return self.declaration()
        if token.kind == TokenKind.KW_IF:
            self.next_token()
            return self.if_statement()
        if token.kind == TokenKind.KW_WHILE:
            self.next_token()
            return self.while_statement()
        if token.kind == TokenKind.KW_FUN:
            self.next_token()
            return self.fun_declaration(is_extern=False)
        if token.kind == TokenKind.KW_STRUCT:
            self.next_token()
            return self.struct_declaration()
        if token.kind == TokenKind.KW_RET:
            self.next_token()
            return self.ret_statement()
        if token.kind == TokenKind.KW_EXTERN:
            self.next_token()
            if self.curr_token().kind == TokenKind.KW_FUN:
                self.match_token(TokenKind.KW_FUN)
                return self.fun_declaration(is_extern=True)
            else:
                self.match_token(TokenKind.KW_STRUCT)
                return self.struct_declaration(is_extern=True)
        if token.kind == TokenKind.KW_ALIAS:
            self.next_token()
            return self.alias_definition()
        if token.kind == TokenKind.KW_IMPORT:
            self.next_token()
            return self.import_statement()
        if token.kind == TokenKind.KW_NAMESPACE:
            self.next_token()
            return self.namespace_statement()
        if token.kind == TokenKind.KW_DEFER:
            self.next_token()
            return self.defer_statement()
        if token.kind == TokenKind.KW_BLOCK:
            self.next_token()
            return self.block_statement()
        if token.kind == TokenKind.KW_MACRO:
            self.next_token()
            return self.macro_statement()

        node = self.token_list_to_tree()
        return node

    def program_statement(self) -> Optional[Node]:
        node = None
        while not self.no_more_lines(check_next_lines=True):
            if node is None:
                node = self.statement()
            else:
                node = glue_statements([node, self.statement()])

            if not self.no_more_lines(check_next_lines=True):
                self.next_line()

        return node

    def compound_statement(self) -> Optional[Node]:
        node = None
        while not self.no_more_lines(check_next_lines=True) and self.curr_token().kind not in (TokenKind.KW_END, TokenKind.KW_ELSE, TokenKind.KW_ELIF):
            if node is None:
                node = self.statement()
            else:
                node = Node(NodeKind.GLUE, void_type,
                            '', node, self.statement())
            self.next_line()

        return node

    def import_statement(self) -> Optional[Node]:
        if Def.fun_name != '':
            print_error('import_statement',
                        'Local imports are not allowed', self)

        module = ''
        while not self.no_more_tokens():
            part = self.match_token(TokenKind.IDENT).value
            module = os.path.join(module, part)

            if not self.no_more_tokens():
                self.match_token(TokenKind.PERIOD)

                if self.no_more_tokens():
                    print_error('import_statement',
                                'Invalid trailing period in import', parser=self)

        module_source = f'{module}.ml'
        if not exists(module_source):
            for module_dir in Def.include_list:
                other_source = os.path.join(module_dir, module_source)
                if exists(other_source):
                    module_source = other_source

        if not exists(module_source):
            print_error('import_statement',
                        f'Module \'{module_source}\' does not exist.', self)

        if module_source in Def.included:
            return None
        Def.included.add(module_source)

        try:
            module_root = Parser().parse(module_source)
        except RecursionError:
            print_error('import_statement',
                        f'Cannot import module "{module_source}" (circular import)', self)
        return module_root

    def namespace_statement(self) -> Optional[Node]:
        if Def.fun_name != '':
            print_error('import_statement',
                        'Local namespaces are not allowed', self)

        namespace = self.match_token(TokenKind.IDENT).value
        self.next_line()

        Def.ident_map[full_name_of_fun(
            namespace, force_global=True)] = VariableMetaKind.NAMESPACE
        Def.module_name_list.append(namespace)
        namespace_node = Node(NodeKind.NAMESPACE, void_type,
                              namespace, self.compound_statement())
        Def.module_name_list.pop()

        return Node(NodeKind.GLUE, void_type, '', namespace_node, Node(NodeKind.END, void_type, 'end'))

    def inject_cond(self, node: Node) -> Node:
        if node_is_cmp(node.kind):
            return node

        return Node(NodeKind.OP_EQ, bool_type, '==', node, Node(NodeKind.TRUE_LIT, bool_type, 'true'))

    def while_statement(self) -> Optional[Node]:
        cond_node = self.token_list_to_tree()
        if cond_node.ntype not in (any_type, bool_type):
            print_error('while_statement',
                        f'Expected a boolean expression, got type {rev_type_of(cond_node.ntype)}', self)

        self.next_line()
        cond_node = self.inject_cond(cond_node)
        body = self.compound_statement()

        node = Node(NodeKind.GLUE, void_type, '', Node(
            NodeKind.WHILE, void_type, '', cond_node, body), Node(NodeKind.END, void_type, 'end'))
        return node

    # An if_statement helper to parse multiple elif statements
    def elif_statement(self) -> Optional[Node]:
        node = None
        cond_node = None
        while not self.no_more_lines() and self.curr_token().kind not in (TokenKind.KW_END, TokenKind.KW_ELSE):
            self.match_token(TokenKind.KW_ELIF)
            cond_node = self.inject_cond(self.token_list_to_tree())

            self.next_line()
            end_node = Node(NodeKind.END, void_type, '')
            elif_node = glue_statements([Node(NodeKind.ELIF, void_type, '',
                                              self.compound_statement(), None, cond_node), end_node])

            if node is None:
                node = elif_node
            else:
                node = Node(NodeKind.GLUE, void_type,
                            '', node, elif_node)

        return node

    def if_statement(self) -> Optional[Node]:
        cond_node = self.token_list_to_tree()
        if cond_node.ntype not in (any_type, bool_type):
            print_error('if_statement',
                        f'Expected a boolean expression, got type {rev_type_of(cond_node.ntype)}', self)

        self.next_line()
        cond_node = self.inject_cond(cond_node)
        end_node = Node(NodeKind.END, void_type, '')

        true_node = glue_statements([Node(NodeKind.IF, void_type, '',
                                          self.compound_statement(), None, cond_node), end_node])

        elif_node = None
        if self.curr_token().kind == TokenKind.KW_ELIF:
            elif_node = self.elif_statement()

        false_node = None
        if self.curr_token().kind == TokenKind.KW_ELSE:
            self.next_line()
            false_node = glue_statements([Node(NodeKind.ELSE, void_type, '',
                                               self.compound_statement()), end_node])

        nodes = [true_node]
        if elif_node is not None:
            nodes.append(elif_node)
        if false_node is not None:
            nodes.append(false_node)

        node = glue_statements(nodes)
        return node

    def ret_statement(self) -> Optional[Node]:
        if Def.fun_name == '':
            print_error('ret_statement',
                        'Cannot return from outside a function', self)

        sig_name = Def.fun_name
        fun_name = Def.fun_name
        if fun_name in Def.fun_sig_map:
            fun_name = Def.fun_sig_map.get(fun_name)

        fun = Def.fun_map.get(fun_name)

        sig = None
        for signature in fun.signatures:
            if signature.name == sig_name:
                sig = signature

        if sig.ret_type == Def.void_type:
            if not self.no_more_tokens():
                print_error('ret_statement',
                            'Cannot return a non-void value from a void function', self)

            return Node(NodeKind.RET, void_type, '')
        else:
            node = self.token_list_to_tree()
            if not type_compatible(NodeKind.FUN_CALL, node.ntype.ckind, sig.ret_type.ckind):
                print_error('ret_statement',
                            'The return type differs from the function\'s', self)

            node = Node(NodeKind.GLUE, void_type, '', Def.deferred,
                        Node(NodeKind.RET, node.ntype, '', node))
            return node

    def fun_declaration(self, is_extern: bool = False) -> Optional[Node]:
        if Def.fun_name != '':
            print_error('fun_declaration',
                        'Local functions are not allowed', self)

        # Needed for extern
        name = self.match_token(TokenKind.IDENT).value
        full_name = full_name_of_fun(name, force_global=True)

        # Needed for extern
        is_variadic = False
        arg_names: list[str] = []
        arg_types: list[VariableType] = []
        elem_types: list[VariableType] = []
        elem_cnts: list[int] = []
        has_args = not self.no_more_tokens() and self.curr_token().kind == TokenKind.LPAREN
        if has_args:
            self.match_token(TokenKind.LPAREN)
            while self.curr_token().kind not in (TokenKind.RPAREN, TokenKind.PER_FUN):
                arg_name = self.match_token(TokenKind.IDENT).value
                self.match_token(TokenKind.COLON)

                type_str = self.curr_token().value
                arg_type = type_of(type_str)
                elem_type = arg_type
                elem_cnt = 0
                self.next_token()

                if not self.no_more_tokens() and self.curr_token().kind == TokenKind.BIT_AND:
                    self.next_token()
                    arg_type = VariableType(ref_ckind, arg_type.ckind)

                elif not self.no_more_tokens() and self.curr_token().kind == TokenKind.MULT:
                    self.next_token()
                    arg_type = VariableType(ptr_ckind, arg_type.ckind)

                elif not self.no_more_tokens() and self.curr_token().kind == TokenKind.LBRACE:
                    self.next_token()
                    arg_type = VariableType(ptr_ckind, arg_type.ckind)
                    elem_cnt = int(self.match_token(TokenKind.INT_LIT).value)
                    self.match_token(TokenKind.RBRACE)
                    self.match_token(TokenKind.MULT)

                if not self.no_more_tokens() and self.curr_token().kind not in (TokenKind.RPAREN, TokenKind.PER_FUN):
                    self.match_token(TokenKind.COMMA)

                arg_names.append(arg_name)
                arg_types.append(arg_type)
                elem_types.append(elem_type)
                elem_cnts.append(elem_cnt)

            token = self.match_token_from(
                (TokenKind.RPAREN, TokenKind.PER_FUN))
            is_variadic = token.kind == TokenKind.PER_FUN

            if is_variadic:
                self.match_token(TokenKind.RPAREN)
        self.match_token(TokenKind.COLON)

        # Needed for extern
        ret_type = type_of(self.curr_token().value)
        self.next_token()

        if not self.no_more_tokens() and self.curr_token().kind == TokenKind.MULT:
            self.next_token()
            ret_type = VariableType(ptr_ckind, ret_type.ckind)

        if not self.no_more_tokens() and self.curr_token().kind == TokenKind.BIT_AND:
            self.next_token()
            ret_type = VariableType(ref_ckind, ret_type.ckind)

        if not self.no_more_tokens():
            print_error('fun_declaration',
                        'Junk after function declaration', self)

        # Computes the signature name
        if is_extern:
            sig_name = full_name
        else:
            sig_name = '_'.join([full_name] + list(map(rev_type_of, arg_types))).replace(
                '*', 'ptr').replace('&', 'ref')

        # ? Temporary
        full_arg_names = []
        Def.fun_name_list.append(sig_name)
        for arg_name in arg_names:
            full_arg_names.append(full_name_of_var(
                arg_name, exhaustive_match=False))
        Def.fun_name_list.pop()

        signature = FunctionSignature(sig_name, len(arg_types), full_arg_names,
                                      arg_types, ret_type, is_extern)
        Def.fun_sig_map[sig_name] = full_name

        check_ident(full_name, VariableMetaKind.FUN, use_mkind=True)
        if Def.ident_map.get(full_name) == VariableMetaKind.FUN:
            fun = Def.fun_map.get(full_name)

            # Checks for conflicting signatures
            if check_signature(fun, signature):
                print_error('fun_declaration',
                            f'New signature of {full_name} ({signature}) conflicts with {_find_signature(fun, signature.arg_types)}', parser=self)

            fun.signatures.append(signature)
        else:
            fun = Function(full_name, len(arg_types), full_arg_names,
                           arg_types, ret_type, 0, is_variadic, is_extern, [signature])

            Def.ident_map[full_name] = VariableMetaKind.FUN
            Def.fun_map[full_name] = fun

        if is_extern:
            return None

        Def.block_cnt = 0
        Def.fun_name = sig_name
        Def.fun_name_list.append(sig_name)
        Def.var_off = 8

        # ? Temporary
        for (arg_name, arg_type, elem_type, elem_cnt) in zip(arg_names, arg_types, elem_types, elem_cnts):
            meta_kind = arg_type.meta_kind()
            Def.ident_map[full_name_of_var(
                arg_name, exhaustive_match=False)] = meta_kind

            Def.var_off += size_of(arg_type.ckind)
            if meta_kind == VariableMetaKind.STRUCT:
                def add_prefix(name: str, arg_name: str = arg_name) -> str:
                    return f'{arg_name}_{name}'

                struct: Structure = Def.struct_map.get(arg_type.name)
                elem_names = struct.elem_names
                struct_elem_types = struct.elem_types
                full_elem_names = list(map(add_prefix, elem_names))
                self.struct_elem_declaration(full_elem_names, struct)

                Def.struct_map[full_name_of_var(arg_name)] = Structure(
                    full_name, struct.vtype, full_elem_names, struct_elem_types)

            elif meta_kind in (VariableMetaKind.PRIM, VariableMetaKind.BOOL):
                Def.var_map[full_name_of_var(arg_name)] = Variable(
                    arg_type, Def.var_off, True)

            elif meta_kind in (VariableMetaKind.PTR, VariableMetaKind.REF):
                Def.ptr_map[full_name_of_var(arg_name)] = Pointer(
                    full_name_of_var(arg_name), elem_cnt, elem_type, Def.var_off, meta_kind == VariableMetaKind.REF, True)

            else:
                print_error('fun_declaration',
                            f'Invalid argument meta kind {meta_kind}', parser=self)

        self.next_line()
        body = self.compound_statement() if fun.ret_type != void_type else (
            Node(NodeKind.GLUE, void_type, '', self.compound_statement(), Def.deferred))

        Def.fun_name = ''
        Def.fun_name_list.pop()
        Def.deferred = None

        # Patch the stack offset
        off = Def.var_off
        align_off = 0 if off % 16 == 0 else 16 - (off % 16)
        fun.off = off + align_off

        node = Node(NodeKind.GLUE, void_type, '',
                    Node(NodeKind.FUN, default_ckind, sig_name, body), Node(NodeKind.END, void_type, 'end'))
        return node

    def struct_declaration(self, is_extern: bool = False) -> Optional[Node]:
        #! BUG: Nested structures
        name = self.match_token(TokenKind.IDENT).value
        vtype = VariableType(struct_ckind, name=name)
        Def.struct_map[name] = Structure(name, vtype, [], [])
        Def.type_map[name] = vtype

        if is_extern:
            return None

        # Parses the structure body
        Def.struct_name = name
        self.next_line()

        node = None
        while not self.no_more_lines() and self.curr_token().kind != TokenKind.KW_END:
            if node is None:
                node = self.declaration(is_struct=True)
            else:
                node = Node(NodeKind.GLUE, void_type,
                            '', node, self.declaration(is_struct=True))
            self.next_line()

        # Creates a constructor-like function
        # ? Requires some solid refactoring
        # ? Duplicated from Parser.fun_declaration
        struct = Def.struct_map.get(name)
        tmp_name = f'{struct.name}_tmp'
        fun_name = name
        # fun_name = f'{name}_new'

        sig_name = '_'.join([fun_name] + list(map(rev_type_of, struct.elem_types))).replace(
            '*', 'ptr').replace('&', 'ref')

        # ? Temporary
        full_arg_names = []
        Def.fun_name_list.append(sig_name)
        for arg_name in struct.elem_names:
            full_arg_names.append(full_name_of_var(
                arg_name, exhaustive_match=False))
        Def.fun_name_list.pop()

        signature = FunctionSignature(sig_name, len(struct.elem_names), full_arg_names,
                                      struct.elem_types, struct.vtype, is_extern)
        Def.fun_sig_map[sig_name] = fun_name

        Def.ident_map[fun_name] = VariableMetaKind.FUN
        Def.fun_map[fun_name] = Function(fun_name, len(struct.elem_names), struct.elem_names, struct.elem_types,
                                         struct.vtype, 0, False, False, [signature])

        def inject_decl(tpl: Tuple[str, str, VariableType]) -> Node:
            #!BUG: No array declaration
            new_name, og_name, var_type = tpl
            elem_acc = Node(NodeKind.ELEM_ACC, struct.vtype, '', Node(
                NodeKind.IDENT, struct.vtype, tmp_name), Node(NodeKind.IDENT, var_type, new_name))

            return Node(NodeKind.OP_ASSIGN, var_type, '=',
                        elem_acc, Node(NodeKind.IDENT, var_type, og_name))

        decl = Node(NodeKind.STRUCT_DECL, struct.vtype, tmp_name)
        ret = Node(NodeKind.RET, struct.vtype, '', Node(
            NodeKind.IDENT, struct.vtype, tmp_name))
        body = glue_statements(list(map(inject_decl, zip(
            full_arg_names, struct.elem_names, struct.elem_types))))
        ctor = Node(NodeKind.FUN, struct.vtype, sig_name,
                    glue_statements([decl, body, ret]))
        end = Node(NodeKind.END, void_type, 'end')

        return glue_statements([Node(NodeKind.STRUCT, void_type, Def.struct_name, node),
                               end, ctor, end])

    def alias_definition(self) -> None:
        if Def.macro_name != '':
            print_error('declaration',
                        f'Type definitions within macro ({Def.macro_name}) are not allowed', self)

        name = self.match_token(TokenKind.IDENT).value
        self.match_token(TokenKind.ASSIGN)

        alias = self.curr_token().value
        self.next_token()

        while not self.no_more_tokens() and self.curr_token().kind == TokenKind.PERIOD:
            self.match_token(TokenKind.PERIOD)
            if self.no_more_tokens():
                print_error('alias_definition',
                            'Invalid trailing period in alias', parser=self)

            if not self.no_more_tokens() and self.curr_token().kind == TokenKind.IDENT:
                alias += f'_{self.match_token(TokenKind.IDENT).value}'

        if alias in Def.ident_map:
            Def.ident_map[name] = VariableMetaKind.ALIAS
            while Def.ident_map.get(alias) == VariableMetaKind.ALIAS:
                alias = Def.alias_map.get(alias)

            Def.alias_map[name] = alias
            return

        #! BUG: This does not parse correctly
        # self.next_token()
        meta_kind = VariableMetaKind.PRIM
        if not self.no_more_tokens() and self.curr_token().kind == TokenKind.MULT:
            self.next_token()
            meta_kind = VariableMetaKind.PTR

        elif not self.no_more_tokens() and self.curr_token().kind == TokenKind.BIT_AND:
            self.next_token()
            meta_kind = VariableMetaKind.REF

        if not self.no_more_tokens():
            print_error('alias_definition',
                        'Junk after type definition', self)

        vtype = type_of(alias)
        if meta_kind == VariableMetaKind.PRIM:
            Def.type_map[name] = vtype
        if meta_kind == VariableMetaKind.PTR:
            Def.type_map[name] = VariableType(ptr_ckind, vtype.ckind)
        if meta_kind == VariableMetaKind.REF:
            Def.type_map[name] = VariableType(ref_ckind, vtype.ckind)

    def defer_statement(self) -> None:
        if Def.macro_name != '':
            return None

        node = self.token_list_to_tree()
        if Def.deferred is None:
            Def.deferred = node
        else:
            Def.deferred = Node(NodeKind.GLUE, void_type,
                                '', Def.deferred, node)

    def block_statement(self) -> Optional[Node]:
        if Def.fun_name == '' and Def.macro_name == '':
            print_error('block_statement',
                        'Global block declarations are not allowed', self)

        name = ''
        unnamed_block = self.no_more_tokens()

        if unnamed_block:
            Def.block_cnt += 1
            name = f'block{Def.block_cnt}'
        else:
            name = self.match_token(TokenKind.IDENT).value

        self.next_line()
        scopeless_block = name.startswith('_')

        if not scopeless_block:
            Def.fun_name_list.append(name)
        block_node = Node(NodeKind.BLOCK, void_type,
                          name, self.compound_statement())
        if not scopeless_block:
            Def.fun_name_list.pop()

        return Node(NodeKind.GLUE, void_type, '', block_node, Node(NodeKind.END, void_type, 'end'))

    def macro_statement(self) -> None:
        if Def.macro_name != '':
            print_error('macro_declaration',
                        'Nested macros are not allowed', self)

        if Def.fun_name != '':
            print_error('macro_declaration',
                        'Local macros are not allowed', self)

        full_name = full_name_of_fun(self.match_token(
            TokenKind.IDENT).value, exhaustive_match=False, force_global=True)

        has_args = not self.no_more_tokens()
        arg_names: list[str] = []
        if has_args:
            self.match_token(TokenKind.LPAREN)

            while self.curr_token().kind != TokenKind.RPAREN:
                arg_name = self.match_token(TokenKind.IDENT).value
                arg_names.append(full_name_of_var(
                    arg_name, exhaustive_match=False))

                if not self.no_more_tokens() and self.curr_token().kind != TokenKind.RPAREN:
                    self.match_token(TokenKind.COMMA)

            self.match_token(TokenKind.RPAREN)
            if not self.no_more_tokens():
                print_error('macro_statement',
                            'Junk after macro declaration', self)

        self.next_line()

        signature = MacroSignature(len(arg_names), arg_names, Parser(self))
        if Def.ident_map.get(full_name) == VariableMetaKind.MACRO:
            macro = Def.macro_map.get(full_name)
            for idx, macro_signature in enumerate(macro.signatures):
                if signature.arg_cnt == macro_signature.arg_cnt:
                    Def.macro_map[full_name].signatures[idx] = signature
                    break
            else:
                Def.macro_map[full_name].signatures.append(signature)

        else:
            check_ident(full_name, VariableMetaKind.MACRO, use_mkind=True)
            Def.ident_map[full_name] = VariableMetaKind.MACRO
            Def.macro_map[full_name] = Macro(
                full_name, len(arg_names), [signature])

        for name in arg_names:
            check_ident(full_name)
            Def.ident_map[name] = VariableMetaKind.ANY

        Def.macro_name = full_name
        _ = self.compound_statement()
        Def.macro_name = ''
        Def.block_cnt = 0

        for name in arg_names:
            if Def.ident_map.get(name) == VariableMetaKind.ANY:
                del Def.ident_map[name]

    def to_node(self, token: Token) -> Node:
        node = None
        kind = self.node_kind_of(token.kind)
        if token.kind != TokenKind.IDENT:
            node = Node(kind, type_of_lit(kind), token.value)
        else:
            full_name = full_name_of_var(token.value)
            node = Node(kind, type_of_ident(full_name), full_name)

        return node

    def array_elem_declaration(self, array: Node, elem: Node, idx: int) -> Node:
        idx_node = self.to_node(Token(TokenKind.INT_LIT, str(idx)))
        acc_node = Node(NodeKind.ARR_ACC, elem.ntype, '', array, idx_node)
        return Node(NodeKind.OP_ASSIGN, elem.ntype, '=', acc_node, elem)

    def array_declaration(self, name: str) -> Node:
        root = None
        elems = []

        while self.curr_token().kind != TokenKind.RBRACE:
            token = self.match_token_from(
                (TokenKind.INT_LIT, TokenKind.CHAR_LIT, TokenKind.IDENT))

            if self.curr_token().kind != TokenKind.RBRACE:
                self.match_token(TokenKind.COMMA)

            elems.append(token)

        arr = Def.arr_map[name]
        if len(elems) > arr.elem_cnt:
            print_error('array_declaration',
                        f'Array {name} can only hold {arr.elem_cnt} elements', self)

        elems.reverse()
        nodes = list(map(self.to_node, elems))

        idx = 0
        arr_node = Node(NodeKind.IDENT, type_of_ident(name), name)

        if len(nodes) == 1:
            root = self.array_elem_declaration(arr_node, nodes.pop(), 0)
        else:
            while len(nodes) > 0:
                if root is None:
                    node = nodes.pop()
                    node2 = nodes.pop()
                    root = Node(NodeKind.GLUE, void_ckind, '', self.array_elem_declaration(
                        arr_node, node, idx), self.array_elem_declaration(arr_node, node2, idx + 1))
                    idx += 2
                else:
                    node = nodes.pop()
                    root = Node(
                        NodeKind.GLUE, void_ckind, '', root, self.array_elem_declaration(arr_node, node, idx))
                    idx += 1

        return root

    def heredoc_declaration(self):
        self.next_line()

        parts = []
        while not self.no_more_lines() and self.curr_token().kind != TokenKind.KW_END:
            parts.append(self.curr_line().lstrip('\t '))
            self.next_line()

        value = ''.join(parts).rstrip('\n')
        return Node(NodeKind.STR_LIT, type_of_lit(NodeKind.STR_LIT), value)

    def struct_elem_declaration(self, names: List[str], og_struct: Structure) -> Optional[Node]:
        for new_name, og_name, var_type in zip(names, og_struct.elem_names, og_struct.elem_types):
            meta_kind = var_type.meta_kind()
            Def.ident_map[new_name] = meta_kind

            if meta_kind in (VariableMetaKind.PRIM, VariableMetaKind.BOOL, VariableMetaKind.ANY):
                Def.var_off += size_of(var_type.ckind)
                Def.var_map[new_name] = Def.var_map[og_name]
                Def.var_map[new_name].off = Def.var_off

            elif meta_kind == VariableMetaKind.ARR:
                arr = Def.arr_map.get(og_name)
                elem_cnt = arr.elem_cnt
                elem_type = arr.elem_type
                Def.var_off += size_of(elem_type.ckind) * elem_cnt
                Def.arr_map[new_name] = arr

            elif meta_kind in (VariableMetaKind.PTR, VariableMetaKind.REF):
                ptr = Def.ptr_map.get(og_name)
                Def.var_off += size_of(var_type.ckind)
                Def.ptr_map[new_name] = ptr

            else:
                print_error('struct_elem_declaration',
                            f'Unknown meta kind {new_name} ({og_name}) {meta_kind}', self)

    def declaration(self, is_struct: bool = False) -> Optional[Node]:
        if Def.macro_name != '':
            print_error('declaration',
                        f'Variable declarations within macro ({Def.macro_name}) are not allowed', self)

        name = self.match_token(TokenKind.IDENT).value

        type_name = ''
        is_implicit = self.curr_token().kind != TokenKind.COLON
        kind, meta_kind = VariableKind.INT64, VariableMetaKind.PRIM
        elem_kind, elem_meta_kind = VariableKind.INT64, VariableMetaKind.PRIM
        if not is_implicit:
            self.match_token(TokenKind.COLON)

            var_type = type_of(self.curr_token().value)
            type_name = var_type.name
            kind, meta_kind = var_type.kind(), var_type.meta_kind()
            elem_kind, elem_meta_kind = kind, meta_kind
            self.next_token()

        elem_cnt = 0
        if not self.no_more_tokens() and self.curr_token().kind == TokenKind.LBRACE:
            self.next_token()

            meta_kind = VariableMetaKind.ARR
            elem_cnt = int(self.match_token(TokenKind.INT_LIT).value)
            self.match_token(TokenKind.RBRACE)

        if not self.no_more_tokens() and self.curr_token().kind == TokenKind.MULT:
            self.next_token()
            meta_kind = VariableMetaKind.PTR

        if not self.no_more_tokens() and self.curr_token().kind == TokenKind.BIT_AND:
            self.next_token()
            meta_kind = VariableMetaKind.REF

        if not self.no_more_tokens():
            self.match_token(TokenKind.ASSIGN)

        var_type = VariableType(VariableCompKind(
            kind, meta_kind), VariableCompKind(elem_kind, elem_meta_kind), name=type_name)
        if is_implicit:
            if self.curr_token().kind == TokenKind.LBRACE:
                print_error(
                    'declaration',
                    'Implicit array declaration is not permitted.', self)

            node = self.token_list_to_tree()
            var_type = node.ntype
            if var_type.ckind == void_ckind:
                print_error('declaration',
                            'Declaration of implicit void primitive is not allowed.', self)

            kind, meta_kind = var_type.kind(), var_type.meta_kind()

            # Decays array to pointer
            if meta_kind == VariableMetaKind.ARR:
                meta_kind = VariableMetaKind.PTR
                elem_cnt = Def.arr_map.get(node.value).elem_cnt

            # Reference correction
            if meta_kind == VariableMetaKind.REF:
                meta_kind = var_type.elem_ckind.meta_kind
                var_type = VariableType(var_type.elem_ckind)

            if meta_kind == VariableMetaKind.PTR:
                elem_kind = var_type.elem_ckind.kind
                elem_meta_kind = var_type.elem_ckind.meta_kind
        else:
            elem_ckind = VariableCompKind(elem_kind, elem_meta_kind)
            if meta_kind == VariableMetaKind.ARR:
                var_type = VariableType(arr_ckind, elem_ckind)
            if meta_kind == VariableMetaKind.BOOL:
                var_type = VariableType(bool_ckind, elem_ckind)
            if meta_kind == VariableMetaKind.PTR:
                var_type = VariableType(ptr_ckind, elem_ckind)
            if meta_kind == VariableMetaKind.REF:
                var_type = VariableType(ref_ckind, elem_ckind)

        is_local = Def.fun_name != ''
        var_name = full_name_of_var(
            name, force_local=True, exhaustive_match=False)
        full_name = var_name if is_local else full_name_of_var(name, True)

        decl_kind = NodeKind.ARR_DECL if meta_kind == VariableMetaKind.ARR else NodeKind.DECLARATION
        if is_struct:
            decl_kind = NodeKind.STRUCT_ARR_DECL if meta_kind == VariableMetaKind.ARR else NodeKind.STRUCT_ELEM_DECL

        if is_struct:
            # full_name = f'{Def.struct_name}_{full_name}'
            Def.struct_map[Def.struct_name].elem_names.append(full_name)
            Def.struct_map[Def.struct_name].elem_types.append(var_type)

        check_ident(full_name)
        Def.ident_map[full_name] = meta_kind

        if meta_kind == VariableMetaKind.STRUCT:
            def add_prefix(name: str) -> str:
                return f'{full_name}_{name}'

            struct = Def.struct_map.get(var_type.name)
            elem_names = struct.elem_names
            elem_types = struct.elem_types
            full_elem_names = list(map(add_prefix, elem_names))
            self.struct_elem_declaration(full_name, struct)

            Def.struct_map[full_name] = Structure(
                full_name, var_type, full_elem_names, elem_types)

            if self.no_more_tokens():
                return Node(NodeKind.STRUCT_DECL, var_type, full_name)

            node = self.token_list_to_tree()
            if var_type != node.ntype:
                print_error('declaration',
                            f'Incompatible assignment between types {rev_type_of(var_type)} and {rev_type_of(node.ntype)}', self)

            return Node(NodeKind.STRUCT_DECL, var_type, '=', Node(NodeKind.IDENT, var_type, full_name), node)

        if meta_kind in (VariableMetaKind.PRIM, VariableMetaKind.BOOL, VariableMetaKind.ANY):
            value = 0 if is_local or is_struct else self.match_token(
                TokenKind.INT_LIT).value
            Def.var_off += size_of(var_type.ckind)
            Def.var_map[full_name] = Variable(
                var_type, Def.var_off, is_local, value)

            if is_struct:
                if not self.no_more_tokens():
                    print_error('declaration',
                                'Junk after struct element declaration', parser=self)

                return Node(decl_kind, var_type, '=', Node(NodeKind.IDENT, var_type, full_name))

            if not is_local:
                return Node(decl_kind, var_type, '=', Node(NodeKind.IDENT, var_type, full_name), Node(NodeKind.INT_LIT, var_type, value))

            node = self.token_list_to_tree()
            if not type_compatible(decl_kind, var_type.ckind, node.ntype.ckind):
                print_error('declaration',
                            f'Incompatible assignment between types {rev_type_of(var_type)} and {rev_type_of(node.ntype)}', self)

            if node.ntype == void_ckind:
                print_error('declaration',
                            'Declaration of void primitive is not allowed.', self)

            return Node(decl_kind, var_type, '=', Node(NodeKind.IDENT, var_type, full_name), node)

        if meta_kind == VariableMetaKind.ARR:
            elem_type = VariableType(VariableCompKind(
                kind, VariableMetaKind.PRIM))
            Def.var_off += size_of(elem_type.ckind) * elem_cnt
            Def.arr_map[full_name] = Array(
                full_name, elem_cnt, elem_type, Def.var_off, is_local)

            if self.no_more_tokens():
                return Node(decl_kind, void_type, full_name)

            self.match_token(TokenKind.LBRACE)

            return Node(NodeKind.GLUE, void_ckind, '', Node(decl_kind, void_type, full_name), self.array_declaration(full_name))

        if meta_kind in (VariableMetaKind.PTR, VariableMetaKind.REF):
            value = 0
            elem_type = VariableType(
                VariableCompKind(elem_kind, elem_meta_kind))
            if not is_local and not is_struct:
                if self.curr_token().kind == TokenKind.BIT_AND:
                    self.next_token()
                    value = self.match_token(TokenKind.IDENT).value
                    if is_local_ident(value):
                        print_error('declaration',
                                    'Global pointers can only point to global variables.', self)

                elif self.curr_token().kind == TokenKind.INT_LIT:
                    value = self.match_token(TokenKind.INT_LIT).value

                else:
                    print_error('declaration',
                                'Can only assign integer literals and global addresses to pointer', self)
            Def.var_off += size_of(var_type.ckind)
            Def.ptr_map[full_name] = Pointer(
                full_name, elem_cnt, elem_type, Def.var_off, meta_kind == VariableMetaKind.REF, is_local, value)

            if is_struct:
                return Node(decl_kind, var_type, '=', Node(NodeKind.IDENT, var_type, full_name))

            if not is_local:
                return Node(decl_kind, VariableType(ref_ckind, elem_kind), '=', Node(NodeKind.IDENT, VariableType(ref_ckind, elem_kind), full_name), Node(NodeKind.INT_LIT, var_type, value))

            node = None
            if self.curr_token().kind == TokenKind.HEREDOC:
                self.next_token()
                node = self.heredoc_declaration()
            else:
                node = self.token_list_to_tree()

            if not type_compatible(decl_kind, var_type.ckind, node.ntype.ckind):
                print_error('declaration',
                            f'Incompatible assignment between types {rev_type_of(var_type)} and {rev_type_of(node.ntype)}', self)

            return Node(decl_kind, var_type, '=', Node(NodeKind.IDENT, var_type, full_name), node)

        print_error('declaration',
                    f'Unknown meta kind {meta_kind}', self)
