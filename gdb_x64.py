import pexpect, sys, StringIO, re
from Tkinter import *
from functools import partial

global oldregister		# 명령어 수행 전의 레지스터 상태
global old_inp			# 이전 명령어를 저장하기 위한 변수.

global addresses		# 일일이 주소를 입력하기 불편함에 따라, 디스어셈블리 패널에서 해당 주소에 대응되는 숫자를 나타내기 위해 사용된다.

global firstAddress		# 디스어셈블리 패널에서 시작 주소를 의미한다. ,vs 명령어에서 사용된다.
global secondAddress	# 디스어셈블리 패널에서 끝 주소.


oldregister = { 'rax' : '0', 'rbx' : '0', 'rcx' : '0', 'rdx' : '0', 'rsi' : '0', 'rdi' : '0',
		'rbp' : '0', 'rsp' : '0', 'r8' : '0', 'r9' : '0', 'r10' : '0', 'r11' : '0',
		'r12' : '0', 'r13' : '0', 'r14' : '0', 'r15' : '0', 'rip' : '0', 'eflags' : '0'}

addresses = {11 : '', 12 : '0', 13 : '', 14 : '', 15 : '', 16 : '', 17 : '', 18 : '',
			 19 : '', 20 : '', 21 : '', 22 : '', 23 : '', 24 : '', 25 : '',
			 26 : '', 27 : '', 28 : '', 29 : '', 30 : '', 31 : '', 32 : '',
			 33 : '', 34 : '', 35 : '', 36 : '', 37 : '', 38 : '', 39 : ''}




"""
디버깅에 사용되는 루틴.

sys.stdout = oldstdout
print()
sys.stdout = newstdout

newstdout.truncate(0)
newstdout.seek(0)
"""




"""
다음 두 함수는 함수 정보 검색을 위해 사용된다.
기본적인 메커니즘과 전제 조건은 README 파일에 설명되어 있다.
apiPanelView() 함수는 API 이름을 panelApi 패널에 표시하며, 해당 API 함수 클릭 시 callback() 함수를 호출한다.
callback() 함수는 shell 명령어를 이용해 해당 함수 이름에 해당하는 man 파일을 실행한다.
"""
def callback(event, param):
	commands = 'shell gnome-terminal -e "man 3 ' + param + '"'
	child.sendline(commands)
	child.expect('\r\n\(gdb\)')
	newstdout.truncate(0)
	newstdout.seek(0)


def apiPanelView(apilist):
	apiName = apilist + '    '
	apiNameTag = apilist
	panelApi.tag_config(apiNameTag, foreground='blue')
	panelApi.tag_bind(apiNameTag, '<Button-1>', partial(callback, param=apiNameTag))
	panelApi.insert(END, apiName, apiNameTag)




"""
디스어셈블리 패널을 위한 함수. 
두 곳에서 사용되는데 한나는 t 같은 일반 제어 명령들과 ,v 자체 명령어이다. 이것은 IP 레지스터가 바뀌었다는 가정 하에 실행된다.
다른 한 곳은 ",vs <address>" 자체 명령어이다. 이것은 IP 레지스터가 바뀌지 않았다는 가정 하에 실행된다.
여부는 isInternal 변수로 구분한다.
"""
def asmview(isInternal, Adres):
	global firstAddress
	global secondAddress
	global oldregister
	global addresses

	# ,vs 명령어에서 사용되는 경우 ip 레지스터를 바꾸지 않고 가상으로 인자로 받은 주소를 IP 어드레스로 여기고 수행한다.
	if isInternal == 0:
		newAddress = hex(int(Adres, 16)-40)
	elif isInternal == 1:
		newAddress = hex(int(oldregister['rip'],16)-30)
		
	newstdout.truncate(0)
	newstdout.seek(0)

	# x/i 명령어를 이용해서 디스어셈블리를 보여준다.
	disCommand = 'x/29i ' + newAddress
	child.sendline(disCommand)
	child.expect('\r\n\(gdb\)')
	dResult = newstdout.getvalue()

	panelDis.delete(1.0, END)
	panelApi.delete(1.0, END)
	
	counts = 0
	i = 10

	for line in dResult.splitlines():
	# 결과로 얻은 라인별로 다음을 수행한다.

		if counts == 0:
		# 첫 라인은 입력한 명령어므로 건너뛴다.
			counts = counts+1
			continue

		if i <= 39:
		# 현재 라인의 주소를 저장한다. 참고로 replace()를 이용해 쉽게 분리한다.
			i = i+1
			forSpl = line.replace('<', ' ').replace(':', ' ').replace('=>', ' ').split()
			addresses[i] = forSpl[0]

		if counts == 1:
		# 처음 라인의 경우 
			counts = counts+1
			firstAddress = line.replace('<', ' ').replace(':', ' ').replace('=>', ' ').split()[0]
			panelDis.insert(END, str(i) + ' ' + line)
			panelDis.insert(END, '\n')
			continue

		if line[:6] == '(gdb) ':
			break
	
		panelDis.insert(END, str(i) + ' ' + line)
		panelDis.insert(END, '\n')
		# 두 번째 라인부터는 매번 주소를 secondAddress에 저장한다. 결국 마지막 라인의 주소가 된다.
		secondAddress = line.replace('<', ' ').replace(':', ' ').replace('=>', ' ').split()[0]

		isApi = line.find('@')
		# 인식하는 함수는 printf@plt 같이 보여지는 함수이다.
		# 이 경우 함수 이름을 넣고 apiPanelView()를 호출한다.
		if isApi != -1:
			forApiName = line[:isApi].rfind('<')
			apilist = line[forApiName+1:isApi]
			apiPanelView(apilist)


	if isInternal == 1:
	# si나 ni같은 명령을 사용한 경우 당연히 현재 IP 레지스터가 =>로 표시된다. 이 경우 빨간색으로 보여준다.
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
	global oldregister

	newstdout.truncate(0)
	newstdout.seek(0)
	child.sendline('00mine')
	# main에서 처리한 00mine 명령어.
	child.expect('\r\n\(gdb\)')
	result = newstdout.getvalue()

	resultHalf = result.find('<>')
	# 토큰으로 <> 표시를 사용하였다.
	rResult = result[:resultHalf-1]
	# 레지스터 관련 결과만 추출.
	sResult = result[resultHalf+3:]
	# 스택 관련 결과만 추출.

	panelReg1.delete(1.0, END)
	panelReg2.delete(1.0, END)

	newregister = {}

	view = ""
	view2 = ""

	for line in rResult.splitlines():

		if line.split()[0] == 'cs':
			break
		elif line.split()[0] == '00mine':
		# 첫 라인은 사용한 명령어가 나오기 때문에 건너뛴다.
			continue

		# 레지스터 별로 newregister에 새로운 값을 채운다.
		regName = line.split()[0]
		newregister[regName] = line.split()[1]
		
		# 보여주는 문자열을 view와 view2로 나누어서 저장한다.
		if regName == 'rax' or regName == 'rdx' or regName == 'rsp' or regName == 'rsi' or regName == 'rip' or regName == 'r8' or regName == 'r10' or regName == 'r12' or regName == 'r14':
			view = view + regName + '\t' + newregister[regName] + '\n'
		elif regName == 'rcx' or regName == 'rbx' or regName == 'rbp' or regName == 'rdi' or regName == 'eflags' or regName == 'r9' or regName == 'r11' or regName == 'r13' or regName == 'r15':
			view2 = view2 + regName + '\t' + newregister[regName] + '\n'
		
		if regName == 'eflags':
			fir = line.find('[')
			sec = line.find(']')
			view2 = view2 + line[fir:sec+1] + '\n'

		
	panelReg1.insert(END, view)
	panelReg2.insert(END, view2)


	# 변경된 레지스터 파란색으로 표시
	for key in oldregister:
		if oldregister[key] != newregister[key]:
			if key == 'rax':
				panelReg1.tag_add("rax", "1.4", "1.22")
				panelReg1.tag_config("rax", foreground="blue")
			elif key == 'rbx':
				panelReg2.tag_add("rbx", "1.4", "1.22")
				panelReg2.tag_config("rbx", foreground="blue")
			elif key == 'rcx':
				panelReg1.tag_add("rcx", "2.4", "2.22")
				panelReg1.tag_config("rcx", foreground="blue")
			elif key == 'rdx':
				panelReg2.tag_add("rdx", "2.4", "2.22")
				panelReg2.tag_config("rdx", foreground="blue")
			elif key == 'rsi':
				panelReg1.tag_add("rsi", "3.4", "3.22")
				panelReg1.tag_config("rsi", foreground="blue")
			elif key == 'rdi':
				panelReg2.tag_add("rdi", "3.4", "3.22")
				panelReg2.tag_config("rdi", foreground="blue")
			elif key == 'rbp':
				panelReg1.tag_add("rbp", "4.4", "4.22")
				panelReg1.tag_config("rbp", foreground="blue")
			elif key == 'rsp':
				panelReg2.tag_add("rsp", "4.4", "4.22")
				panelReg2.tag_config("rsp", foreground="blue")
			elif key == 'r8':
				panelReg1.tag_add("r8", "5.3", "5.21")
				panelReg1.tag_config("r8", foreground="blue")
			elif key == 'r9':
				panelReg2.tag_add("r9", "5.3", "5.21")
				panelReg2.tag_config("r9", foreground="blue")
			elif key == 'r10':
				panelReg1.tag_add("r10", "6.4", "6.22")
				panelReg1.tag_config("r10", foreground="blue")
			elif key == 'r11':
				panelReg2.tag_add("r11", "6.4", "6.22")
				panelReg2.tag_config("r11", foreground="blue")
			elif key == 'r12':
				panelReg1.tag_add("r12", "7.4", "7.22")
				panelReg1.tag_config("r12", foreground="blue")
			elif key == 'r13':
				panelReg2.tag_add("r13", "7.4", "7.22")
				panelReg2.tag_config("r13", foreground="blue")
			elif key == 'r14':
				panelReg1.tag_add("r14", "8.4", "8.22")
				panelReg1.tag_config("r14", foreground="blue")
			elif key == 'r15':
				panelReg2.tag_add("r15", "8.4", "8.22")
				panelReg2.tag_config("r15", foreground="blue")
			elif key == 'rip':
				panelReg1.tag_add("rip", "9.4", "9.22")
				panelReg1.tag_config("rip", foreground="blue")
			elif key == 'eflags':
				panelReg2.tag_add("eflags", "9.6", "9.20")
				panelReg2.tag_config("eflags", foreground="blue")

	
	oldregister = newregister



	# 디스어셈블리 패널은 해당 함수에서 처리한다.
	# outview()에서 사용되므로 isInternal 변수는 1을 준다.
	asmview(1, 0)



	# 스택 관련 내용이다.
	panelStack.delete(1.0, END)
	
	i = 0
	spAddress = sResult.split()[0]
	spAddress = "0" + spAddress[:-1]
	spAddress = hex(int(spAddress, 16))
	for stacks in sResult.split('0x'):
		if i == 0 or i == 3 or i == 6 or i == 9 or i == 12 or i == 15 or i == 18 or i == 21:
			i = i+1
			continue
		if stacks == '(gdb)':
			break
		stacks = "0x" + stacks
		if stacks.find('\r\n') != -1:
			stacks = stacks[:-2]
		panelStack.insert(END, spAddress)
		panelStack.insert(END, '\t\t')
		spAddress = hex(int(spAddress, 16)+8)
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
	global addresses

	newstdout.truncate(0)
	newstdout.seek(0)

	# 입력으로 받은 명령어를 inp에 넣는다.
	# 입력 없이 Enter키가 눌러진 경우 이전 명령어 old_inp를 다시 inp에 넣어준다.
	if not vari.get():
		inp = old_inp
	else:
		inp = vari.get()

	firstinp = inp.split()[0]
	old_inp = inp


	# 아래에 해당하는 경우는 제어 명령어들, 즉 왼쪽 창들을 업데이트시켜야 하는 명령어들이다.
	# 공통되는 부분이 많아서 한번에 정리하였다.
	if firstinp == 'si' or firstinp == 'ni' or firstinp == 'c' or firstinp == 'continue' or firstinp == 'finish' or firstinp == 'return':
		child.sendline(inp)
		child.expect('\r\n\(gdb\) ')
		tpResult = newstdout.getvalue()
		isEnd = tpResult.find('exited normally')
		isRes = 0
		if tpResult.splitlines()[1].find('0x') == -1:
			isRes = 1

		if isRes == 1:
		# 출력 결과가 나오는 경우.
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, tpResult)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '(gdb) ')
			panelCommand.config(state=DISABLED)
			outview()
		elif isEnd == -1:
		# 일반적인 경우
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '(gdb) ')
			panelCommand.config(state=DISABLED)
			outview()
		else:
		# 종료된 경우
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, tpResult)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '(gdb) ')
			panelCommand.config(state=DISABLED)


	#
	# 종료 명령어
	elif firstinp == 'q' or firstinp == 'quit':
	# q 명령어를 사용한 경우 자체적으로 종료시킨다.
		child.close()
		root.destroy()	


	#
	# 다음은 자체 명령어들이다.
	elif firstinp[0] == ',':

		if firstinp == ',b':
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			
			num = int(inp[3:5])
			inp = "break *" + addresses.get(num)
			child.sendline(inp)
			child.expect('\r\n\(gdb\) ')
			
			panelCommand.insert(END, newstdout.getvalue())
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '(gdb) ')
			panelCommand.config(state=DISABLED)

		elif firstinp == ',wt':
		# Windbg의 wt 명령도 간단하게 사용하게 하기 위해 자체 명령어를 만든 후 주소 대신 라인 번호를 입력받게 하였다.
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '(gdb) ')
			panelCommand.config(state=DISABLED)
			
			num = int(inp[4:6])
			inp = "break *" + addresses.get(num)
			child.sendline(inp)
			child.expect('\r\n\(gdb\) ')
			brNum = newstdout.getvalue().split()[3]

			child.sendline('c')
			child.expect('\r\n\(gdb\) ')
			child.sendline('d ' + brNum)
			child.expect('\r\n\(gdb\) ')

			outview()

		elif firstinp == ',api':
		# 함수 이름을 인자로 넣으면 API 패널에서 클릭한 것과 같이 해당 함수에 대한 도움말을 보여준다.
			param = inp.split()[1]
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '(gdb) ')
			panelCommand.config(state=DISABLED)
			commands = 'shell gnome-terminal -e "man 3 ' + param + '"'
			child.sendline(commands)
			child.expect('\r\n\(gdb\) ')

		elif firstinp == ',v':
		# 어지간한 경우에 자동으로 왼쪽 창들을 업데이트 시키지만 그렇지 않는 경우도 존재한다.
		# 예를들면 직접 ip 레지스터를 수정하는 경우가 그렇다. 이 경우에는 이 명령어를 사용하여 왼쪽 창을 업데이트시킨다.
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
			panelCommand.insert(END, '(gdb) ')
			panelCommand.config(state=DISABLED)

		elif firstinp == ',vs':
		# 왼쪽 창의 디스어셈블리 창에서 ",vs <address>" 처럼 인자로 받은 주소를 기준으로 디스어셈블리를 보여준다.
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

		
	#
	# 다음은 기타 명령어들로서 오른쪽 텍스트 창에만 결과를 보여준다.
	else:
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




"""
main 함수.
Tkinter와 winpexpect 위주로 정리되어 있다.
"""
if __name__ == "__main__":

	# 인자 정리.
	if len(sys.argv) == 1:
		print("Need Argument")
		quit()

	arg1 = sys.argv[1]


	# Tkinter를 이용한 GUI 초기화.
	root = Tk()
	frame = Frame(root)
	frame.pack()
	bottomframe = Frame(root)
	bottomframe.pack()

	# frame1은 왼쪽 화면을 의미한다.
	frame1 = Frame(frame, height=50, width=80)
	frame1.grid(row=0, column=0, sticky=W+N)
	# panelDis는 디스어셈블리 패널이다.
	panelDis = Text(frame1, height=29, width=80)
	panelDis.grid(row=7, column=0, sticky=W+N)
	# panelReg1은 왼쪽 레지스터 패널이다.
	panelReg1 = Text(frame1, height=6, width=40)
	panelReg1.grid(row=0, column=0, sticky=W+N)
	# panelReg2는 오른쪽 레지스터 패널이다.
	panelReg2 = Text(frame1, height=6, width=40)
	panelReg2.grid(row=0, column=0, sticky=E+N)
	# panelStack은 스택 패널이다.
	panelStack = Text(frame1, height=12, width=80)
	panelStack.grid(row=33, column=0, sticky=W+N)

	# frame2는 오른쪽 화면을 의미한다.
	frame2 = Frame(frame, height=50, width=70)
	frame2.grid(row=0, column=80, sticky=W+N)
	# panelCommand는 명령어 결과를 보여주는 패널이다.
	panelCommand = Text(frame2, height=45, width=70)
	panelCommand.grid(row=0, column=80, sticky=W+N)
	# panelApi는 명령어 패널 아래에 위치한 패널로서 디스어셈블리 패널에서 보이는 API 함수들을 보여준다.
	# 해당 API 이름을 클릭하면 도움말 파일을 이용해 API 정보를 볼 수 있다.
	panelApi = Text(frame2, height=5, width=70)
	panelApi.grid(row=0, column=80, sticky=W+S)


	# pexpect를 이용해 gdb의 입출력을 관리한다.
	# 다음은 gdb를 이용한 초기 명령어이다. 바이너리를 오픈한 후 설정 및 start를 실행한다.
	# > gdb [바이너리 이름]
	# (gdb) start
	# (gdb) disas
	# (gdb) set pagination off
	# 참고로 결과 페이지를 한 번에 보여주게 하는 설정이다.
	# (gdb) set disassembly-flavor intel
	# 참고로 Intel 형태의 디스어셈블리를 보여주게 하는 설정이다.
	firstCommand = "gdb " + arg1
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

	# define 명령어로 필요한 명령어를 연결한다.
	# 사실 .gdbinit 파일에 다음 내용을 추가함으로써 이것을 대신할 수 있다.
	#
	# .gdbinit
	#
	# define 00mine
	#	i r
	#	echo <>
	#	x/16a $sp
	# end
	child.sendline('define 00mine')
	child.expect('\r\n\>')
	child.sendline('i r')
	child.expect('\r\n\>')
	child.sendline('echo <>')
	child.expect('\r\n\>')
	child.sendline('x/16a $sp')
	child.expect('\r\n\>')
	child.sendline('end')
	child.expect('\r\n\(gdb\) ')

	panelCommand.insert(END, '(gdb) ')
	newstdout.truncate(0)
	newstdout.seek(0)
	outview()


	# 입력 받은 명령어를 변수 vari에 저장한 후 func 함수를 통해 콜백 형식으로 사용된다.
	vari = StringVar()
	E5 = Entry(frame2, textvariable=vari)
	E5.grid(row=40, column=80, sticky=S)
	E5.bind('<Return>', func)

	root.mainloop()
	child.close()
