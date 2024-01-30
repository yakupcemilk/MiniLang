import "number"
import "../../stdlib/va_utils"
import "../../stdlib/cstdlib"

fun custom_printf(format: int8*, ...): void
    let va_list: int64[3]

    asm "stack_snapshot"
    va_start(va_list)
    va_arg(va_list)
    asm "stack_rewind"

    # DBG
    # asm "lea str_13(%rip), %rdi"
    # asm "mov %rsp, %rsi"
    # asm "xor %rax, %rax"
    # asm "call printf"

    let flag: int8 = 0
    let repeat: int8 = 0
    let arr: int8[500]
    let str: int8* = arr
    let str_idx = 0
    let format_idx = 0

    while format[format_idx] != 0 
        while format[format_idx] != '%' 
            # printf("char: '%c'\n", format[format_idx])
            str[str_idx] = format[format_idx]
            format_idx = format_idx + 1
            str_idx = str_idx + 1
        end

        flag = 0 
        repeat = 1
        while repeat == 1
            format_idx = format_idx + 1
            if format[format_idx] == '-' 
                flag = flag | minus_flag 
                # puts("minus-flag")
            else
                if format[format_idx] == '0' 
                    flag = flag | zero_flag 
                    # puts("zero-flag")
                else
                    if format[format_idx] == '+' 
                        flag = flag | plus_flag 
                        # puts("plus-flag")
                    else
                        if format[format_idx] == ' ' 
                            flag = flag | space_flag 
                            # puts("space_flag")
                        else
                            repeat = 0
                        end
                    end
                end
            end
        end

        let width = 0
        if format[format_idx] == '*' 
            width = va_arg(va_list) 
        else: 
            let cnt = 0 
            while isdigit(format[format_idx]) > 0
                cnt = cnt + 1
                format_idx = format_idx + 1
            end

            if cnt > 0
                width = strnToU64(sub(add(format, format_idx), cnt), cnt)
            end
        end

        if format[format_idx] == '%' 
            str[str_idx] = '%' 
            str_idx = str_idx + 1
            # puts("percent")
        else
            if format[format_idx] == 's'
                let buf = cstr(va_arg(va_list))
                #  printf("string: %s\n", buf)
                strcpy(add(str, str_idx), buf) 
                str_idx = str_idx + strlen(buf)
            else
                if format[format_idx] == 'd'
                    let repr = char((format[format_idx] == 'd'))
                    let num: int64 = va_arg(va_list)
                    number(add(str, str_idx), num, repr, flag, width) 
                    # puts("signed iteger")
                else
                    if format[format_idx] == 'u'
                        # puts("unsigned iteger")
                        let repr = char((format[format_idx] == 'd'))
                        let num: int64 = va_arg(va_list) 
                        number(add(str, str_idx), num, repr, flag, width) 
                    end
                end
            end
        end

        format_idx = format_idx + 1
    end

    puts(arr)
end
end