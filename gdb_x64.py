import pexpect, sys, StringIO, re
from Tkinter import *

global old_inp
global oldregister
global firstAddress
global secondAddress

oldregister = { 'rax' : '0', 'rbx' : '0', 'rcx' : '0', 'rdx' : '0', 'rsi' : '0', 'rdi' : '0',
		'rbp' : '0', 'rsp' : '0', 'r8' : '0', 'r9' : '0', 'r10' : '0', 'r11' : '0',
		'r12' : '0', 'r13' : '0', 'r14' : '0', 'r15' : '0', 'rip' : '0', 'eflags' : '0'}




"""
디스어셈블리 창을 위한 함수. 
두 곳에서 사용되는데 한 곳은 si나 ni 같은 일반 제어 명령들에서 스택 및 레지스터 창과 함께 사용된다.
다른 한 곳은 ",vs <address>" 자체 명령어이다.
"""
def asmview(isInternal, Adres):
	global firstAddress
	global secondAddress

	if isInternal == 0:
		newAddress = hex(int(Adres, 16)-30)
	elif isInternal == 1:
		newAddress = hex(int(oldregister['rip'],16)-40)
		
	newstdout.truncate(0)
    newstdout.seek(0)
	disCommand = 'x/25i ' + newAddress
    child.sendline(disCommand)
    child.expect('\r\n\(gdb\)')
    dResult = newstdout.getvalue()
    panelDis.delete(1.0, END)
	counts = 0
	for line in dResult.splitlines():
		if counts == 0:
			counts = counts+1
			continue	
		if counts == 1:
			counts = counts+1
			firstAddress = line.split()[0]
			panelDis.insert(END, line)
			panelDis.insert(END, '\n')
			continue
		if line[:6] == '(gdb) ':
			break
        	panelDis.insert(END, line)
		panelDis.insert(END, '\n')
		secondAddress = line.split()[0]
	preLine = panelDis.search("=>", "1.0", END)
	preLineEnd = panelDis.search("\n", preLine, END)
	panelDis.tag_add("reds", preLine, preLineEnd)
	panelDis.tag_config("reds", foreground="red")




"""
왼쪽 디스어셈블리, 레지스터, 스택 창을 보여주는 함수.
일반적으로 si나 ni 같은 제어 명령어를 사용하면 세 곳이 모두 업데이트된다.
참고로 디스어셈블리 창은 내부적으로 위에 정의된 asmview() 함수를 사용한다.
"""
def outview():

	# 레지스터 패널을 보여준다.
	newstdout.truncate(0)
	newstdout.seek(0)
	child.sendline('i r')	
	child.expect('\r\n\(gdb\)')
	rResult = newstdout.getvalue()

	panelReg.delete(1.0, END)

	newregister = {}

	for line in rResult.splitlines():
		if line.split()[0] == 'cs':
			break
		elif line.split()[1] == 'r':
			continue	# for first line

		regName = line.split()[0]
		newregister[regName] = line.split()[1]
		
		panelReg.insert(END, regName)
		panelReg.insert(END, '\t\t')
		panelReg.insert(END, newregister[regName])
		if oldregister[regName] != newregister[regName]:
			if regName == 'rax':
				panelReg.tag_add("rax", "1.5", "1.23")
				panelReg.tag_config("rax", foreground="blue")
			elif regName == 'rbx':
				panelReg.tag_add("rbx", "2.5", "2.23")
                                panelReg.tag_config("rbx", foreground="blue")
			elif regName == 'rcx':
				panelReg.tag_add("rcx", "3.5", "3.23")
                                panelReg.tag_config("rcx", foreground="blue")
			elif regName == 'rdx':
				panelReg.tag_add("rdx", "4.5", "4.23")
                                panelReg.tag_config("rdx", foreground="blue")
			elif regName == 'rsi':
				panelReg.tag_add("rsi", "5.5", "5.23")
                                panelReg.tag_config("rsi", foreground="blue")
			elif regName == 'rdi':
				panelReg.tag_add("rdi", "6.5", "6.23")
                                panelReg.tag_config("rdi", foreground="blue")
			elif regName == 'rbp':
				panelReg.tag_add("rbp", "7.5", "7.23")
                                panelReg.tag_config("rbp", foreground="blue")
			elif regName == 'rsp':
				panelReg.tag_add("rsp", "8.5", "8.23")
                                panelReg.tag_config("rsp", foreground="blue")
			elif regName == 'r8':
				panelReg.tag_add("r8", "9.4", "9.22")
                                panelReg.tag_config("r8", foreground="blue")
                        elif regName == 'r9':
                                panelReg.tag_add("r9", "10.4", "10.22")
                                panelReg.tag_config("r9", foreground="blue")
                        elif regName == 'r10':
                                panelReg.tag_add("r10", "11.5", "11.23")
                                panelReg.tag_config("r10", foreground="blue")
                        elif regName == 'r11':
                                panelReg.tag_add("r11", "12.5", "12.23")
                                panelReg.tag_config("r11", foreground="blue")
                        elif regName == 'r12':
                                panelReg.tag_add("r12", "13.5", "13.23")
                                panelReg.tag_config("r12", foreground="blue")
                        elif regName == 'r13':
                                panelReg.tag_add("r13", "14.5", "14.23")
                                panelReg.tag_config("r13", foreground="blue")
                        elif regName == 'r14':
                                panelReg.tag_add("r14", "15.5", "15.23")
                                panelReg.tag_config("r14", foreground="blue")
                        elif regName == 'r15':
                                panelReg.tag_add("r15", "16.5", "16.23")
                                panelReg.tag_config("r15", foreground="blue")
                        elif regName == 'rip':
                                panelReg.tag_add("rip", "17.5", "17.23")
                                panelReg.tag_config("rip", foreground="blue")
			elif regName == 'eflags':
				panelReg.tag_add("eflags", "18.6", "18.20")
                                panelReg.tag_config("eflags", foreground="blue")

		panelReg.insert(END, '\n')
		oldregister[regName] = newregister[regName]


	# 어셈블리 패널을 보여준다.
	asmview(1, 0)


	# 스택 패널을 보여준다.
	panelStack.delete(1.0, END)
	newstdout.truncate(0)
        newstdout.seek(0)
        child.sendline('x/16gx $sp')
        child.expect('\r\n\(gdb\)')
        sResult = newstdout.getvalue()
	i = 0
	spAddress = sResult.split()[2]
	spAddress = spAddress[:-1]
	spAddress = hex(int(spAddress, 16))
	for stacks in sResult.split():
		if i < 3 or i == 7 or i == 12:
			i = i+1
			continue
		if stacks == '(gdb)':
			break
		panelStack.insert(END, spAddress)
                panelStack.insert(END, '\t\t')
                spAddress = hex(int(spAddress, 16)+4)
		panelStack.insert(END, stacks)
		panelStack.insert(END, '\n')
		i = i+1




"""
명령어 입력과 관련된 콜백 함수이다.
각종 명령어들을 받아들이고 처리한다.
제어 명령어는 outview()를 통한 업데이트를 수행하고,
기타 명령어들은 텍스트 창에 결과를 보여준다.
마지막으로 자체 명령어들도 따로 정의하였다.
"""
def func(event):

	global old_inp
	global firstAddress
	global secondAddress

	newstdout.truncate(0)
	newstdout.seek(0)

	if not vari.get():
		inp = old_inp
	else:
		inp = vari.get()

	firstinp = inp.split()[0]
	old_inp = inp

	if firstinp == 'si' or firstinp == 'ni' or firstinp == 'c' or firstinp == 'continue' or firstinp == 'finish' or firstinp == 'return':
		child.sendline(inp)
		child.expect('\r\n\(gdb\) ')
		panelCommand.config(state=NORMAL)
		panelCommand.insert(END, inp)
		panelCommand.insert(END, '\n')
		panelCommand.insert(END, '(gdb) ')
		panelCommand.config(state=DISABLED)
		tpResult = newstdout.getvalue()
		outview()

	# 다음은 자체 명령어들이다.
	elif firstinp == ',v':
		# 어지간한 경우에 자동으로 왼쪽 창들을 업데이트 시키지만 그렇지 않는 경우도 존재한다.
		# 예를들면 직접 rip를 수정하는 경우가 그렇다. 이 경우에는 이 명령어를 사용하여 왼쪽 창들을 업데이트시킨다.
		panelCommand.config(state=NORMAL)
		panelCommand.insert(END, inp)
		panelCommand.insert(END, '\n')
		panelCommand.insert(END, '(gdb) ')
		panelCommand.config(state=DISABLED)
		outview()

	elif firstinp == ',c':
		# clear 명령어. 오른쪽 텍스트 창을 지운다.
		panelCommand.config(state=NORMAL)
		panelCommand.delete('1.0', END)
		panelCommand.config(state=DISABLED)

	elif firstinp == ',vs':
		# 왼쪽 디스어셈블리 창에서 인자로 받은 주소를 기준으로 디스어셈블리를 보여준다.
		# u옵션 즉 ",vs u"와 같이 사용하면 위 화면을 보여주고 d 옵션을 사용하면 아래 화면을 보여준다.
		panelCommand.config(state=NORMAL)
		panelCommand.insert(END, inp)
		panelCommand.insert(END, '\n')
		panelCommand.insert(END, '(gdb) ')
		panelCommand.config(state=DISABLED)
		if inp[4] == 'u':
			asmview(0, firstAddress)
		elif inp[4] == 'd':
			asmview(0, secondAddress)
		else:
			asmview(0, inp[4:])

	else:
		# 기타의 경우로 오른쪽 텍스트 창에 결과를 보여준다.
		child.sendline(inp)
		child.expect('\r\n\(gdb\) ')	
		line = newstdout.getvalue()
		panelCommand.config(state=NORMAL)
                panelCommand.insert(END, inp)
                panelCommand.insert(END, '\n')
		panelCommand.insert(END, line)
		panelCommand.config(state=DISABLED)
	E5.delete(0, 'end')
	panelCommand.see('end')


if __name__ == "__main__":

	argv = sys.argv[1]

	root = Tk()
	frame = Frame(root)
	frame.pack()
	bottomframe = Frame(root)
	bottomframe.pack()

	frame1 = Frame(frame, height=50, width=80)
	frame1.grid(row=0, column=0, sticky=W+N)
	panelDis = Text(frame1, height=25, width=80)
	panelDis.grid(row=8, column=0, sticky=W+N)
	panelReg = Text(frame1, height=10, width=80)
	panelReg.grid(row=0, column=0, sticky=W+N)
	panelStack = Text(frame1, height=12, width=80)
	panelStack.grid(row=33, column=0, sticky=W+N)

	frame2 = Frame(frame, height=50, width=70)
	frame2.grid(row=0, column=80, sticky=W+N)
	panelCommand = Text(frame2, height=40, width=70)
	panelCommand.grid(row=0, column=80, sticky=W+N)


	firstCommand = "gdb " + argv
	child = pexpect.spawn(firstCommand)
	oldstdout = sys.stdout
	newstdout = StringIO.StringIO()
	sys.stdout = newstdout
	child.logfile_read = sys.stdout

	child.expect('\r\n\(gdb\) ')
	child.sendline('start')
	child.expect('\r\n\(gdb\) ')
	child.sendline('disas')
	child.expect('\r\n\(gdb\) ')
	child.sendline('set pagination off')
	child.expect('\r\n\(gdb\)')
	child.sendline('set disassembly-flavor intel')
	child.expect('\r\n\(gdb\)')

	outview()

	vari = StringVar()
	E5 = Entry(frame2, textvariable=vari)
	E5.grid(row=40, column=80, sticky=S)
	E5.bind('<Return>', func)

	root.mainloop()
	child.close()
