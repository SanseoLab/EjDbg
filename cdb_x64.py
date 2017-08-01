import winpexpect, sys, io, re
from tkinter import *
from functools import wraps


global oldregister
global old_inp
global newrip
global nowmodule
global premodule
global iatEnd
global iatStart
global firstAddress
global secondAddress

oldregister = { 'rax' : '0000000000000000', 'rbx' : '0000000000000000', 'rcx' : '0000000000000000', 'rdx' : '0000000000000000', 'rsi' : '0000000000000000', 
				'rdi' : '0000000000000000', 'rip' : '0000000000000000', 'rsp' : '0000000000000000', 'rbp' : '0000000000000000', 'r8' : '0000000000000000', 
				'r9' : '0000000000000000', 'r10' : '0000000000000000', 'r11' : '0000000000000000', 'r12' : '0000000000000000', 'r13' : '0000000000000000', 
				'r14' : '0000000000000000', 'r15' : '0000000000000000' }




def memoize(func):
	cache = {}
	@wraps(func)
	def wrap(*args):
		if args not in cache:
			cache[args] = func(*args)
		return cache[args]
	return wrap




@memoize
def extractGrave(string, grave='`'):
	try:
		nov = string.replace('`', '')
		return nov
	except ValueError:
		return -1


@memoize
def plusGrave(string, grave='`'):
	try:
		nov = string[:8] + '`' + string[8:17]
		return nov
	except ValueError:
		return -1


# 괄호 안의 주소를 찾기 위한 함수.
@memoize
def extract(string, start='(', stop=')'):
	try:
		nov = string[string.index(start)+1:string.index(stop)]
		return nov
	except ValueError:
		return -1


@memoize
def apifunc(sym):
	child.sendline('.printf "%y", poi(' + sym + ')')
	child.expect('0:000> ')
	return newstdout.getvalue()




# api 함수 이름들은 디스어셈블리 창에 보여주기 위해서는 iat를 찾고 처리해야 하는데 그러기 위한 함수.
# 처음과 outview() 실행 시마다 실행된다.
def findiat():
	global iatEnd
	global iatStart
	global nowmodule

	# 현재 모듈의 imagebase를 구한다.
	child.sendline('lm')
	child.expect('0:000> ')
	lmResult = newstdout.getvalue()
	newstdout.truncate(0)
	newstdout.seek(0)
	for line in lmResult.splitlines():
		if line.find(nowmodule) >= 1:
			imgbase = line[:17]
			break

	child.sendline('!dh -f'+ imgbase)
	child.expect('0:000> ')
	imginfo = newstdout.getvalue()
	foriat = ""

	for lineOfimginfo in imginfo.splitlines():
		if lineOfimginfo.find("Import Address Table Directory") >= 1:
			foriat = lineOfimginfo
			break

	iatstartnsize = re.findall(r'[0-9A-F]+', foriat, re.I)

	iatStartAddress = iatstartnsize[0]
	iatEndAddress = int(iatstartnsize[0], 16) + int(iatstartnsize[1], 16)
	hexiatEndAddress = hex(iatEndAddress)
	imgbase = extractGrave(imgbase)
	iatStart = int(iatStartAddress, 16) + int(imgbase, 16)
	iatEnd = int(hexiatEndAddress, 16) + int(imgbase, 16)
	newstdout.truncate(0)
	newstdout.seek(0)




"""
디스어셈블리 창을 위한 함수. 
두 곳에서 사용되는데 한 곳은 t나 p 같은 일반 제어 명령들에서 스택 및 레지스터 창과 함께 사용된다.
다른 한 곳은 ",vs <address>" 자체 명령어이다.
"""
def asmview(preins, isinternal, adres):

	global firstAddress
	global secondAddress
	global newrip

	panelDis.delete(1.0, END)
	newstdout.truncate(0)
	newstdout.seek(0)

	if isinternal == 0:
		newrip = adres
	ubins = "ub " + newrip + " l9"

	child.sendline(ubins)
	child.expect('0:000> ')
	ubResult = newstdout.getvalue()
	resultLN = ubResult.find('\n')
	resultEnd = ubResult.find('0:000> ')

	firstAddress = extractGrave(ubResult[resultLN+1:resultLN+18])

	view = ubResult[resultLN+1:resultEnd-1] + "\n"
	newstdout.truncate(0)
	newstdout.seek(0)

	uins = "u " + newrip + " l12"
	child.sendline(uins)
	child.expect('0:000> ')
	uResult = newstdout.getvalue()
	counts = 0

	if isinternal == 1:
		forview = preins + '\n'
		for line in uResult.splitlines():
			if counts == 0 or counts == 1:
				counts = counts+1
				continue
			else:
				forview = forview + line + '\n'
	elif isinternal == 0:
		forview = ""
		for line in uResult.splitlines():
			if counts == 0:
				counts = counts+1
				continue
			else:
				forview = forview + line + '\n'

	view = view + forview + "\n\n"

	for line in view.splitlines():

		if line == '0:000> ':
			break

		secondAddress = extractGrave(line[:17])

		newstdout.truncate(0)
		newstdout.seek(0)
		isCallExist = line.find("call")
		callAddress = extract(line)
		if callAddress != -1:
			callAddress = extractGrave(callAddress)
		if isCallExist != -1 and callAddress != -1:
			sym = callAddress
			if iatStart <= int(callAddress, 16) <= iatEnd:
				apilist = apifunc(sym)
				newstdout.truncate(0)
				newstdout.seek(0)
				apilist = apilist[:-7]
				line = line +'\t' + apilist + '\n'
				panelDis.insert(END, line)

				apiFirst = panelDis.search(apilist, "1.0", END)
				apiEnd = panelDis.search('\n', apiFirst, END)
				panelDis.tag_add("two", apiFirst, apiEnd)
				panelDis.tag_config("two", foreground="blue")
				continue

			else:
				indirect = apifunc(sym)
				newstdout.truncate(0)
				newstdout.seek(0)
				if indirect[:4] == "25ff":
					inp = 'u ' + callAddress
					child.sendline(inp)
					child.expect('0:000> ')
					indr = newstdout.getvalue()
					newstdout.truncate(0)
					newstdout.seek(0)
					addr = extract(indr.splitlines()[1])
					sym2 = str(addr)
					apilist = apifunc(sym2)
					apilist = apilist[:-7]
					line = line +'\t' + apilist + '\n'
					panelDis.insert(END, line)

					apiFirst = panelDis.search(apilist, "1.0", END)
					apiEnd = panelDis.search('\n', apiFirst, END)
					panelDis.tag_add("two", apiFirst, apiEnd)
					panelDis.tag_config("two", foreground="blue")

					continue

		panelDis.insert(END, line + '\n')

	if isinternal == 1:
		first = "1.0"
		while True:
			newrip2 = plusGrave(newrip)
			ripfirst = panelDis.search(newrip2, first, END)
			if not ripfirst:
				break
			ripend = panelDis.search('\n', ripfirst, END)
			panelDis.tag_add("one", ripfirst, ripend)
			panelDis.tag_config("one", foreground="red")
			first = ripend

	newstdout.truncate(0)
	newstdout.seek(0)
	




"""
왼쪽 디스어셈블리, 레지스터, 스택 창을 보여주는 함수.
일반적으로 t나 p 같은 제어 명령어를 사용하면 세 곳이 모두 업데이트된다.
참고로 디스어셈블리 창은 내부적으로 위에 정의된 disview() 함수를 사용한다.
"""
def outview():
	global oldregister
	global newrip
	global premodule
	global nowmodule

	# 아래는 레지스터 창과 관련된 내용이다.
	newstdout.truncate(0)
	newstdout.seek(0)
	child.sendline('r')
	child.expect('0:000> ')
	rResult = newstdout.getvalue()

	newregister = { 'rax' : rResult[4:20], 'rbx' : rResult[25:42], 'rcx' : rResult[46:62], 'rdx' : rResult[67:83], 'rsi' : rResult[88:104], 
					'rdi' : rResult[109:125], 'rip' : rResult[130:146], 'rsp' : rResult[151:167], 'rbp' : rResult[172:188], 'r8' : rResult[193:209], 
					'r9' : rResult[214:230], 'r10' : rResult[235:251], 'r11' : rResult[256:272], 'r12' : rResult[277:293], 'r13' : rResult[298:314], 
					'r14' : rResult[319:335], 'r15' : rResult[340:356] }

	view = 'rax = ' + newregister['rax'] + '\t\t' + 'rbx = ' + newregister['rbx'] + "\n"
	view = view + 'rcx = ' + newregister['rcx'] + '\t\t' + 'rdx = ' + newregister['rdx'] + "\n"
	view = view + 'rsi = ' + newregister['rsi'] + '\t\t' + 'rdi = ' + newregister['rdi'] + "\n"
	view = view + 'rip = ' + newregister['rip'] + '\t\t' + 'rsp = ' + newregister['rsp'] + "\n"
	view = view + 'rbp = ' + newregister['rbp'] + '\t\t' + 'r8  = ' + newregister['r8'] + "\n"
	view = view + 'r9  = ' + newregister['r9']  + '\t\t' + 'r10 = ' + newregister['r10'] + "\n"
	view = view + 'r11 = ' + newregister['r11'] + '\t\t' + 'r12 = ' + newregister['r12'] + "\n"
	view = view + 'r13 = ' + newregister['r13'] + '\t\t' + 'r14 = ' + newregister['r14'] + "\n"
	view = view + 'r15 = ' + newregister['r15'] + "\n"
	view = view + "" + "\n\n"
	panelDis.delete(1.0, END)
	panelReg.delete(1.0, END)
	panelStack.delete(1.0, END)
	panelReg.insert(END, view)

	for key in oldregister:
		if oldregister[key] != newregister[key]:
			if key == 'rax':
				panelReg.tag_add("rax", "1.6", "1.22")
				panelReg.tag_config("rax", foreground="blue")
			elif key == 'rbx':
				panelReg.tag_add("rbx", "1.30", "1.46")
				panelReg.tag_config("rbx", foreground="blue")
			elif key == 'rcx':
				panelReg.tag_add("rcx", "2.6", "2.22")
				panelReg.tag_config("rcx", foreground="blue")
			elif key == 'rdx':
				panelReg.tag_add("rdx", "2.30", "2.46")
				panelReg.tag_config("rdx", foreground="blue")
			elif key == 'rsi':
				panelReg.tag_add("rsi", "3.6", "3.22")
				panelReg.tag_config("rsi", foreground="blue")
			elif key == 'rdi':
				panelReg.tag_add("rdi", "3.30", "3.46")
				panelReg.tag_config("rdi", foreground="blue")
			elif key == 'rip':
				panelReg.tag_add("rip", "4.6", "4.22")
				panelReg.tag_config("rip", foreground="blue")
			elif key == 'rsp':
				panelReg.tag_add("rsp", "4.30", "4.46")
				panelReg.tag_config("rsp", foreground="blue")
			elif key == 'rbp':
				panelReg.tag_add("rbp", "5.6", "5.22")
				panelReg.tag_config("rbp", foreground="blue")
			elif key == 'r8':
				panelReg.tag_add("rbp", "5.30", "5.46")
				panelReg.tag_config("rbp", foreground="blue")
			elif key == 'r9':
				panelReg.tag_add("r9", "6.6", "6.22")
				panelReg.tag_config("r9", foreground="blue")
			elif key == 'r10':
				panelReg.tag_add("r10", "6.30", "6.46")
				panelReg.tag_config("r10", foreground="blue")
			elif key == 'r11':
				panelReg.tag_add("r11", "7.6", "7.22")
				panelReg.tag_config("r11", foreground="blue")
			elif key == 'r12':
				panelReg.tag_add("r12", "7.30", "7.46")
				panelReg.tag_config("r12", foreground="blue")
			elif key == 'r13':
				panelReg.tag_add("r13", "8.6", "8.22")
				panelReg.tag_config("r13", foreground="blue")
			elif key == 'r14':
				panelReg.tag_add("r14", "8.30", "8.46")
				panelReg.tag_config("r14", foreground="blue")
			elif key == 'r15':
				panelReg.tag_add("r15", "9.6", "9.22")
				panelReg.tag_config("r15", foreground="blue")

	oldregister = newregister


	# 현재 명령어 라인을 preins 변수로 미리 저장해 놓는다.
	# 또한 동시에 현재 모듈 이름을 nowmodule 변수에 저장해 놓는다.
	preins = ""
	counts = 0
	for line in rResult.splitlines():
		if counts == 8:
			nowmodule = re.split(r"[\+\!]", line)[0]
		elif counts == 9:
			preins = line
		counts = counts+1
	newstdout.truncate(0)
	newstdout.seek(0)


	# 이전 모듈과 현재 모듈이 다르다면 findiat()를 호출한다.
	if premodule != nowmodule:
		findiat()
		premodule = nowmodule


	# 아래는 디스어셈블리 창을 호출하는 부분이다.
	# 받는 인자로는 현재 명령어 라인(굳이 따로 설정하는 이유는 windbg의 경우 현재 명령어 라인에서만 제공해주는 정보가 있기 때문이다. api 명이나 분기 여부 등),
	# outview()에서 호출되었는지 여부(이 경우에는 1이다)가 있다.
	# newrip는 전역 변수로 설정해서 인자로 넣지는 않았다.

	newrip = newregister['rip']
	isinternal = 1
	asmview(preins, isinternal, "")


	# 아래는 스택 창을 보여주는 부분이다.
	# 기본적으로 dds esp 명령어에 dda esp 명령어의 결과물을 붙여서 내놓는다.
	child.sendline('dqs rsp l18')
	child.expect('0:000> ')
	stackResult = newstdout.getvalue()
	newstdout.truncate(0)
	newstdout.seek(0)
	child.sendline('dqa @rsp l18')
	child.expect('0:000> ')
	stackResult2 = newstdout.getvalue()
	stackResultEnd = stackResult.find('0:000> ')

	stackResult = stackResult[:stackResultEnd-1]
	stackResult2 = stackResult2[:stackResultEnd-1]
	newstackResult = ""
	for line, line2 in zip(stackResult.splitlines(), stackResult2.splitlines()):
		line = line + "\t" + line2[18:]
		newstackResult = newstackResult + line + "\n"

	view2 = newstackResult + "\n"
	panelStack.insert(END, view2)

	newstdout.truncate(0)
	newstdout.seek(0)




"""
명령어 입력과 관련된 콜백 함수이다.
각종 명령어들을 받아들이고 처리한다.
제어 명령어는 outview()를 통한 업데이트를 수행하고,
기타 명령어들은 텍스트 창에 결과를 보여준다.
마지막으로 자체 명령어들도 따로 정의하였다.
"""
def func(event):
	global old_inp
	global newrip
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
	
	# 아래에 해당하는 경우는 제어 명령어들, 즉 왼쪽 창들을 업데이트시켜야 하는 명령어들이다.
	# 공통되는 부분이 많아서 한번에 정리하였다.
	if firstinp == 't' or firstinp == 'p' or firstinp == 'g' or firstinp == 'wt' or firstinp == 'ta' or firstinp == 'pa' or firstinp == 'tc' or firstinp == 'pc' or firstinp == 'tt' or firstinp == 'pt' or firstinp == 'tct' or firstinp == 'pct' or firstinp == 'th' or firstinp == 'ph' or firstinp == 'gc' or firstinp == 'gu' or firstinp == 'gh' or firstinp == 'gn' :
		child.sendline(inp)
		child.expect('0:000> ')
		tpResult = newstdout.getvalue()
		# x64의 경우에는 레지스터의 결과가 안나오고 모듈 이름이 나온다.
		# 여러 예외도 안해봤고 여러 예외적인 사항은 테스트를 안해봐서 우선 이렇게 한다. 즉 bp는 잘 처리된다.
		if nowmodule == re.split(r"[\+\!]", tpResult)[0]:
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '0:000> ')
			panelCommand.config(state=DISABLED)
		else:
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, "\n")
			panelCommand.insert(END, tpResult.splitlines()[0])
			panelCommand.insert(END, "\n")
			panelCommand.insert(END, '0:000> ')
			panelCommand.config(state=DISABLED)
		outview()

	# 다음은 자체 명령어들이다.
	elif firstinp == ',v':
		# 어지간한 경우에 자동으로 왼쪽 창들을 업데이트 시키지만 그렇지 않는 경우도 존재한다.
		# 예를들면 직접 rip를 수정하는 경우가 그렇다. 이 경우에는 이 명령어를 사용하여 왼쪽 창들을 업데이트시킨다.
		panelCommand.config(state=NORMAL)
		panelCommand.insert(END, inp)
		panelCommand.insert(END, '\n')
		panelCommand.insert(END, '0:000> ')
		panelCommand.config(state=DISABLED)
		outview()
	elif firstinp == ',c':
		# clear 명령어. 오른쪽 텍스트 창을 지운다.
		panelCommand.config(state=NORMAL)
		panelCommand.delete('1.0', END)
		panelCommand.config(state=DISABLED)
	elif firstinp == ',vs':
		# 왼쪽 디스어셈블리 창에서 인자로 받은 주소를 기준으로 디스어셈블리를 보여준다.
		# 그냥 텍스트 창에서 u 명령어를 사용해도 되지만 굳이 이 자체 명령어를 만든 이유는
		# 디스어셈블리 창에서는 api 이름을 보여주고 ub와 혼합되어 위, 아래 명령어들을 모두 보여주기 때문이다.
		# u옵션 즉 ",vs u"와 같이 사용하면 위 화면을 보여주고 d 옵션을 사용하면 아래 화면을 보여준다.
		panelCommand.config(state=NORMAL)
		panelCommand.insert(END, inp)
		panelCommand.insert(END, '\n')
		panelCommand.insert(END, '0:000> ')
		panelCommand.config(state=DISABLED)
		if inp[4] == 'u':
			asmview(0, 0, firstAddress)
		elif inp[4] == 'd':
			asmview(0, 0, secondAddress)
		else:
			asmview(0, 0, inp[4:])
	else:
		# 기타의 경우로 오른쪽 텍스트 창에 결과를 보여준다.
		child.sendline(inp)
		child.expect('0:000> ')
		line = newstdout.getvalue()
		panelCommand.config(state=NORMAL)
		panelCommand.insert(END, inp)
		panelCommand.insert(END, '\n')
		panelCommand.insert(END, line)
		panelCommand.config(state=DISABLED)

	E5.delete(0, 'end')
	panelCommand.see('end')




"""
main 함수.
Tkinter와 winpexpect 위주로 정리되어 있다.
"""
if __name__ == "__main__":
	global premodule
	global nowmodule
	global iatEnd
	global iatStart

	argv = sys.argv[1]

	root = Tk()
	frame = Frame(root)
	frame.pack()
	bottomframe = Frame(root)
	bottomframe.pack()


	frame1 = Frame(frame, height=50, width=110)
	frame1.grid(row=0, column=0, sticky=W+N)
	panelDis = Text(frame1, height=30, width=110)
	panelDis.grid(row=8, column=0, sticky=W+N)
	panelReg = Text(frame1, height=8, width=110)
	panelReg.grid(row=0, column=0, sticky=W+N)
	panelStack = Text(frame1, height=12, width=110)
	panelStack.grid(row=33, column=0, sticky=W+N)

	frame2 = Frame(frame, height=50, width=70)
	frame2.grid(row=0, column=110, sticky=W+N)
	panelCommand = Text(frame2, height=48, width=70)
	panelCommand.grid(row=0, column=110, sticky=W+N)

	firstCommand = "cdb " + argv
	child = winpexpect.winspawn(firstCommand)
	oldstdout = sys.stdout
	newstdout = io.StringIO()
	sys.stdout = newstdout
	child.logfile_read = sys.stdout
	child.expect('0:000> ')
	child.sendline('bp $exentry')
	child.expect('0:000> ')
	child.sendline('g')
	child.expect('0:000> ')
	newstdout.truncate(0)
	newstdout.seek(0)


	# 모듈 및 iat 관련 변수들을 초기화한다.
	# 이후 outview() 함수에서부터 사용된다.
	premodule = ""
	nowmodule = ""
	iatStart = 0
	iatEnd = 0
	outview()
	newstdout.truncate(0)
	newstdout.seek(0)

	vari = StringVar()
	E5 = Entry(frame2, textvariable=vari)
	E5.grid(row=48, column=110, sticky=N)
	E5.bind('<Return>', func)
	root.mainloop()
	child.close()
