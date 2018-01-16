from numba import types, ir_utils, ir
from numba.ir_utils import (compile_to_numba_ir, replace_arg_nodes)
from numba.typing import signature
from numba.typing.templates import infer_global, AbstractTemplate
from numba.extending import models, register_model, lower_builtin
import hpat
import numpy as np

def read_ros_images():
    return 0

# inner functions

def open_bag():
    return 0

def get_msg_count():
    return 0

def get_image_dims():
    return 0

def read_ros_images_inner():
    return 0

def read_ros_images_inner_parallel():
    return 0


def _handle_read_images(lhs, rhs):
    fname = rhs.args[0]
    def f(file_name):  # pragma: no cover
        bag = hpat.ros.open_bag(file_name)
        num_msgs = hpat.ros.get_msg_count(bag)
        m,n = hpat.ros.get_image_dims(bag)
        # hpat.cprint(num_msgs, m, n)
        A = np.empty((num_msgs, m, n, 3), dtype=np.uint8)
        s = hpat.ros.read_ros_images_inner(A, bag)

    f_block = compile_to_numba_ir(f, {'np': np, 'hpat': hpat}).blocks.popitem()[1]
    replace_arg_nodes(f_block, [fname])
    nodes = f_block.body[:-3]  # remove none return
    A_var = nodes[-2].value.args[0]
    #A_var = nodes[-1].target
    nodes.append(ir.Assign(A_var, lhs, lhs.loc))
    return nodes

class BagFileType(types.Opaque):
    def __init__(self):
        super(BagFileType, self).__init__(name='BagFileType')

bag_file_type = BagFileType()

register_model(BagFileType)(models.OpaqueModel)

@infer_global(read_ros_images)
class ReadMsgImageTyper(AbstractTemplate):
    def generic(self, args, kws):
        assert not kws
        assert len(args) == 1
        return signature(types.Array(types.uint8, 4, 'C'), *args)

@infer_global(open_bag)
class BagOpenTyper(AbstractTemplate):
    def generic(self, args, kws):
        assert not kws
        assert len(args) == 1
        return signature(bag_file_type, *args)

@infer_global(get_msg_count)
class MsgCountTyper(AbstractTemplate):
    def generic(self, args, kws):
        assert not kws
        assert len(args) == 1
        return signature(types.intp, *args)

@infer_global(get_image_dims)
class MsgDimsTyper(AbstractTemplate):
    def generic(self, args, kws):
        assert not kws
        assert len(args) == 1
        return signature(types.UniTuple(types.intp, 2), *args)

@infer_global(read_ros_images_inner)
class ReadInnerTyper(AbstractTemplate):
    def generic(self, args, kws):
        assert not kws
        assert len(args) == 2
        return signature(types.int32, *args)

from numba import cgutils
from llvmlite import ir as lir
import ros_cpp
import llvmlite.binding as ll
ll.add_symbol('open_bag', ros_cpp.open_bag)
ll.add_symbol('get_msg_count', ros_cpp.get_msg_count)
ll.add_symbol('get_image_dims', ros_cpp.get_image_dims)

@lower_builtin(open_bag, hpat.string_type)
def lower_open_bag(context, builder, sig, args):
    fnty = lir.FunctionType(lir.IntType(8).as_pointer(),
                            [lir.IntType(8).as_pointer()])
    fn = builder.module.get_or_insert_function(fnty, name="open_bag")
    return builder.call(fn, args)

@lower_builtin(get_msg_count, bag_file_type)
def lower_get_msg_count(context, builder, sig, args):
    fnty = lir.FunctionType(lir.IntType(64),
                            [lir.IntType(8).as_pointer()])
    fn = builder.module.get_or_insert_function(fnty, name="get_msg_count")
    return builder.call(fn, args)

@lower_builtin(get_image_dims, bag_file_type)
def lower_get_image_dims(context, builder, sig, args):
    out_ptr = cgutils.alloca_once(builder, lir.IntType(64), 2)
    out_typ = lir.ArrayType(lir.IntType(64), 2)
    fnty = lir.FunctionType(lir.VoidType(),
                            [lir.IntType(64).as_pointer(),
                            lir.IntType(8).as_pointer()])
    fn = builder.module.get_or_insert_function(fnty, name="get_image_dims")
    builder.call(fn, [out_ptr] + args)
    out_ptr_fixed_typ = builder.bitcast(out_ptr, out_typ.as_pointer())
    return builder.load(out_ptr_fixed_typ)
