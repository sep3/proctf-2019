package ae.hitb.proctf.drone_racing.programming.stack

import ae.hitb.proctf.drone_racing.programming.Compiler
import ae.hitb.proctf.drone_racing.programming.exhaustive
import ae.hitb.proctf.drone_racing.programming.language.*
import java.util.*

class StatementToStackCompiler : Compiler<Program, StackProgram> {
    data class JumpPlaceholder(
        val position: Int,
        val fillFunction: (Int) -> StackStatement,
        val traceException: Exception = RuntimeException()
    )

    class CompilationEnvironment {
        val stringPool = mutableListOf<CharArray>()

        val unknownStackContent = listOf<StackStatement>()
        val stackContent = mutableMapOf<Int, List<StackStatement>>(0 to emptyList())

        fun saveStringToPool(stringLiteral: StringLiteral): Int {
            val charArray = stringLiteral.value.toCharArray()
            return stringPool.withIndex().firstOrNull { (_, v) -> v.contentEquals(charArray) }?.index ?: run {
                val result = stringPool.size
                stringPool.add(stringLiteral.value.toCharArray())
                result
            }
        }

        class ExitHandler

        val exitHandlersStack = Stack<ExitHandler>().apply { }

    }

    override fun compile(source: Program): StackProgram {
        val environment = CompilationEnvironment()
        val functionBodies = source.functionDeclarations.associateWith { environment.compileFunction(it) }
        return StackProgram(functionBodies, source.mainFunction, environment.stringPool)
    }

    private fun CompilationEnvironment.compileFunction(function: FunctionDeclaration): List<StackStatement> {
        val source = function.body

        stackContent.clear()
        stackContent[0] = emptyList()

        check(exitHandlersStack.isEmpty())
        val returnHandler = CompilationEnvironment.ExitHandler()
        exitHandlersStack.push(returnHandler)

        val statementsDebugStack = Stack<Statement>()
        val exprsDebugStack = Stack<Expression>()
        val program = arrayListOf<Triple<Any, Statement?, Expression?>>()

        fun mergeStackContents(instructionNumber: Int, content: List<StackStatement>) {
            stackContent.compute(instructionNumber) { _, existing ->
                if (existing != null && existing !== unknownStackContent) {
                    check(existing.size == content.size) {
                        "Stacks do not match:\n$content\n$existing"
                    }
                }
                content
            }
        }

        fun emit(statement: StackStatement, atIndex: Int = program.size) {
            val currentStack = stackContent[atIndex]!!
            val modifiedStack : List<StackStatement> = when (statement) {
                is Ld, is LdParam, is PushInt, is PushString, is PushPooled -> currentStack + statement
                is St, is Jz, Ret1, Pop -> currentStack.dropLast(1)
                is Call -> {
                    val cutStack = currentStack.dropLast(statement.function.parameterNames.size)
                    if (statement.function.returnType == FunctionType.VOID)
                        cutStack
                    else
                        cutStack + statement
                }
                is Unop -> currentStack.dropLast(1) + statement
                is Binop -> currentStack.dropLast(2) + statement
                is Jmp, TransEx, Ret0, Nop -> currentStack
                TransEx -> currentStack
            }
            when (statement) {
                is Jmp -> {
                    mergeStackContents(statement.nextInstruction, modifiedStack)
                    stackContent[atIndex + 1] = unknownStackContent
                }
                is Jz -> {
                    mergeStackContents(statement.nextInstruction, modifiedStack)
                    mergeStackContents(atIndex + 1, modifiedStack)
                }
                else -> mergeStackContents(atIndex + 1, modifiedStack)
            }
            if (atIndex == program.size) {
                val entry = Triple(statement, statementsDebugStack.lastOrNull(), exprsDebugStack.lastOrNull())
                program.add(entry)
            } else {
                val (insn, st, ex) = program[atIndex]
                check(insn is JumpPlaceholder)
                program[atIndex] = Triple(statement, st, ex)
            }
        }

        fun nextInsn() = program.size

        fun emitJumpPlaceholder(fillFunction: (Int) -> StackStatement): JumpPlaceholder {
            val currentStack = stackContent[program.size]!!
            stackContent[program.size + 1] = when (fillFunction) {
                ::Jmp ->  currentStack
                ::Jz -> currentStack.dropLast(1)
                else -> throw UnsupportedOperationException()
            }

            val jumpPlaceholder = JumpPlaceholder(program.lastIndex + 1, fillFunction, RuntimeException())
            val entry = Triple(jumpPlaceholder, statementsDebugStack.lastOrNull(), exprsDebugStack.lastOrNull())
            program.add(entry)
            return jumpPlaceholder
        }

        fun fillJumpPlaceholder(placeholder: JumpPlaceholder, jumpTo: Int) {
            val placeholderEntry = program[placeholder.position]
            check(placeholderEntry.first === placeholder)
            emit(placeholder.fillFunction(jumpTo), placeholder.position)
        }

        fun compileExpression(expression: Expression) {
            exprsDebugStack.push(expression)
            when (expression) {
                is IntLiteral -> emit(PushInt(expression))
                is StringLiteral -> {
                    val stringIndex = saveStringToPool(expression)
                    emit(PushPooled(stringIndex))
                    emit(Call(Intrinsic.STRDUP))
                }
                is Variable -> emit(Ld(expression))
                is Param -> emit(LdParam(expression))
                is UnaryOperation -> {
                    compileExpression(expression.operand)
                    emit(Unop(expression.kind))
                }
                is BinaryOperation -> {
                    compileExpression(expression.left)
                    compileExpression(expression.right)
                    emit(Binop(expression.kind))
                }
                is FunctionCall -> {
                    for (e in expression.argumentExpressions)
                        compileExpression(e)
                    emit(Call(expression.functionDeclaration))
                }
            }.exhaustive
            check(exprsDebugStack.pop() == expression)
        }

        fun compileStatement(statement: Statement) {
            statementsDebugStack.push(statement)
            @Suppress("IMPLICIT_CAST_TO_ANY")
            when (statement) {
                Pass -> emit(Nop)
                is AssignStatement -> {
                    compileExpression(statement.expression)
                    emit(St(statement.variable))
                }
                is IfStatement -> {
                    compileExpression(statement.condition)
                    val pJumpIfNot = emitJumpPlaceholder(::Jz)
                    compileStatement(statement.trueBranch)
                    val pJumpOverFalseBranch =
                        if (statement.falseBranch != Pass)
                            emitJumpPlaceholder(::Jmp) else
                            JumpPlaceholder(-1, ::Jmp, RuntimeException())
                    fillJumpPlaceholder(pJumpIfNot, nextInsn())
                    compileStatement(statement.falseBranch)
                    if (statement.falseBranch != Pass)
                        fillJumpPlaceholder(pJumpOverFalseBranch, nextInsn())
                    Unit
                }
                is WhileStatement -> {
                    val expressionLabel = nextInsn()
                    compileExpression(statement.condition)
                    val pJumpOutside = emitJumpPlaceholder(::Jz)
                    compileStatement(statement.body)
                    emit(Jmp(expressionLabel))
                    fillJumpPlaceholder(pJumpOutside, nextInsn())
                }
                is ChainStatement -> {
                    compileStatement(statement.leftPart)
                    compileStatement(statement.rightPart)
                }
                is ReturnStatement -> {
                    check(function.returnType != FunctionType.VOID) { "Can't return from void function" }
                    compileStatement(AssignStatement(returnDataVariable, statement.expression))
                }
                is FunctionCallStatement -> {
                    if (statement.functionCall.functionDeclaration.returnType != FunctionType.VOID) {
                        compileExpression(statement.functionCall)
                        emit(Pop)
                    } else
                        compileExpression(statement.functionCall)
                }
            }.exhaustive
            check(statementsDebugStack.pop() == statement)
        }

        if (function.returnType == FunctionType.STRING)
            emit(PushString(StringLiteral("")))
        else
            emit(PushInt(IntLiteral(0)))
        emit(St(returnDataVariable))

        compileStatement(source)

        if (function.returnType == FunctionType.VOID)
            emit(Ret0)
        else {
            emit(Ld(returnDataVariable))
            emit(Ret1)
        }

        check(exitHandlersStack.peek() == returnHandler)
        exitHandlersStack.pop()

        return program.mapIndexed { idx, (insn, st, ex) ->
            if (insn is StackStatement) {
                insn
            } else {
                val forStString = st?.let { " at statement $it" }.orEmpty()
                val forExString = ex?.let { " at expression $it" }.orEmpty()
                throw IllegalStateException("Empty placeholder at $idx$forStString$forExString",
                                            (insn as JumpPlaceholder).traceException)
            }
        }
    }
}

