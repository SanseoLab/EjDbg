import winpexpect, sys, io, re
from tkinter import *
from functools import wraps
from functools import partial


global oldregister		# 명령어 수행 전의 레지스터 상태
global old_inp			# 이전 명령어를 저장하기 위한 변수.
global neweip			# 명령어 실행 후 변경된 EIP 레지스터.

global addresses		# 일일이 주소를 입력하기 불편함에 따라, 디스어셈블리 패널에서 해당 주소에 대응되는 숫자를 나타내기 위해 사용된다.

global nowmodule		# main과 outview()에서 볼 수 있으며 현재 모듈의 이름을 보여준다.
global premodule		# 이전 모듈을 보여준다.
						# 이 변수들은 현재 모듈이 바이너리인지 아니면 kernel32.dll 같은 DLL인지 확인할 때 사용된다.

global iatEnd			# IAT의 끝 주소
global iatStart			# IAT의 시작 주소

global firstAddress		# 디스어셈블리 패널에서 시작 주소를 의미한다. ,vs 명령어에서 사용된다.
global secondAddress	# 디스어셈블리 패널에서 끝 주소.

global indirectStart	# 디버그 모드로 컴파일 하는 경우에 흔히 볼 수 있는 jmp를 이용한 간접 호출 시에 사용된다.
global endOfCode		# 코드 영역의 끝 주소.
global isJmp			# jmp를 이용한 간접 호출이 존재하는지 여부를 나타내는 플래그.


oldregister = { 'eax' : '', 'ebx' : '', 'ecx' : '', 'edx' : '', 'esi' : '', 'edi' : '', 
			 'eip' : '', 'esp' : '', 'ebp' : '', 'efl' : '' }

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
입력을 받고 해당 입력에 따라 출력을 내는 함수들 중에서 외부적인 요인에 관여하지 않는 경우,
출력 값을 미리 저장해 놓아서 다음에 같은 인자를 받은 경우 간단하게 출력 결과만 반환하는 메커니즘다.
해당 메커니즘을 사용하고 싶은 함수 위에 @memoize를 붙이면 사용할 수 있다.
결과적으로 해당 함수를 다시 실행할 필요 없이 같은 결과를 냄으로써 오버헤드를 줄이는데 사용된다.
예를들어 apifunc() 함수의 경우 여러 번 반복적으로 실행될 수 밖에 없는데 이 함수는 특징이 인자로 받는 sym이 같은 경우에는 반환 값도 같다.
이에 따라 오버헤드가 큰 child.sendline()과 child.expect()를 여러 번 수행할 필요 없이 같은 인자를 받는 경우에는 저장된 같은 결과를 반환시킨다.
"""
def memoize(func):
	cache = {}
	@wraps(func)
	def wrap(*args):
		if args not in cache:
			cache[args] = func(*args)
		return cache[args]
	return wrap




"""
괄호 안의 주소를 찾기 위한 함수.
"""
@memoize
def extract(string, start='(', stop=')'):
	try:
		nov = string[string.index(start)+1:string.index(stop)]
		return nov
	except ValueError:
		return -1




"""
poi를 이용해 API 이름을 얻어내는데 사용된다.
"""
@memoize
def apifunc(sym):
	
	child.sendline('.printf "%y", poi(' + sym + ')')
	child.expect('0:000> ')

	return newstdout.getvalue()



"""
다음 두 함수는 API 정보 검색을 위해 사용된다.
기본적인 메커니즘과 전제 조건은 README 파일에 설명되어 있다.
apiPanelView() 함수는 API 이름을 panelApi 패널에 표시하며, 해당 API 함수 클릭 시 callback() 함수를 호출한다.
callback() 함수는 .shell 명령어를 이용해 해당 API 이름에 해당하는 도움말 파일을 실행한다.
"""
def callback(event, param):
	if param[-4:] == "Stub":
	# 현재 운영체제가 Windows 10이라서 뒤에 Stub 붙은 API들이 많다. 그래서 이 경우 그냥 Stub 이전까지만 검색한다.
		param = param[:-4]

	commands = ".shell -x C:\\" + "\"Program Files (x86)\"" + "\\\"Microsoft Help Viewer\"" + "\\v2.2\\HlpViewer.exe /catalogName VisualStudio14 /helpQuery \"method=f1&query=" + param + "\""
	child.sendline(commands)
	child.expect('0:000> ')
	newstdout.truncate(0)
	newstdout.seek(0)


def apiPanelView(apilist):
	apiNameFirst = apilist.find("!")
	forApiName = apilist[apiNameFirst+1:].split()[0]
	if forApiName[0] == "_":
		return
	apiName = forApiName + "\t"
	apiNameTag = forApiName

	panelApi.tag_config(apiNameTag, foreground="blue")
	panelApi.tag_bind(apiNameTag, "<Button-1>", partial(callback, param=apiNameTag))

	panelApi.insert(END, apiName, apiNameTag)




"""
api 함수 이름들은 디스어셈블리 창에 보여주기 위해서는 IAT의 영역을 알아야 하는데 이를 위한 함수.
IAT 영역 외에도 간접 jmp 호출이 존재하는 영역도 찾는다.
처음과 outview() 실행 시에 사용된다.
"""
def findiat():
	global iatEnd				# IAT 종료 주소
	global iatStart				# IAT 시작 주소
	global nowmodule			# 새로운 모듈 이름

	global indirectStart		# 간접 jmp 호출의 시작 주소
	global endOfCode			# 코드 영역의 종료 주소
	global isJmp				# 간접 jmp 호출의 존재 여부를 저장한다.


	# 현재 모듈의 imagebase를 구한다.
	child.sendline('lm')
	child.expect('0:000> ')
	lmResult = newstdout.getvalue()
	newstdout.truncate(0)
	newstdout.seek(0)
	for line in lmResult.splitlines():
		if line.find(nowmodule) >= 1:
			imgbase = line[:8]
			break

	# !dh 명령어를 이용해 여러 결과를 얻는다.
	child.sendline('!dh -f'+ imgbase)
	child.expect('0:000> ')
	imginfo = newstdout.getvalue()
	foriat = ""
	forJmp = ""

	for lineOfimginfo in imginfo.splitlines():
		if lineOfimginfo.find("size of code") >= 1:
		# 결과 중 하나는 code 섹션의 크기이다.
			forJmp = lineOfimginfo

		if lineOfimginfo.find("Import Address Table Directory") >= 1:
		# 다른 하나는 Optional Directory에서 Import Address Table Directory를 구한다.
			foriat = lineOfimginfo
			break

	iatstartnsize = re.findall(r'[0-9A-F]+', foriat, re.I)
	iatStartAddress = iatstartnsize[0]

	if iatStartAddress == "0":
	# 만약 Import Address Table Directory가 0이라면 추가적인 방식이 필요한데, 아직 구현하지 않았으며 대신 Error를 커맨드라인에 남긴다.
		sys.stdout = oldstdout
		print("Error : Finding IAT (" + nowmodule +")")
		sys.stdout = newstdout


	# 다음은 IAT 영역을 구하는 방식이다.
	iatEndAddress = int(iatstartnsize[0], 16) + int(iatstartnsize[1], 16)
	hexiatEndAddress = hex(iatEndAddress)
	iatStart = int(iatStartAddress, 16) + int(imgbase, 16)
	iatEnd = int(hexiatEndAddress, 16) + int(imgbase, 16)


	# 다음은 간접 jmp들이 코드 섹션의 마지막에 모여있다는 것에 착안하여 그 영역을 구한다.
	# 참고로 오버헤드를 줄이기 위해 최대한 명령을 입력하지 않는다는 목적으로 아래를 구현한다.
	# 메커니즘은 먼저 IAT 내부인 경우에도 마찬가지로 call 함수에 사용되는 주소가 간접 jmp들의 영역이라면 추가적인 행위를 수행하는 것이다.
	# call이 호출하는 주소가 이 두가지가 아니라면 추가적인 행위를 하지 않음으로써 오버헤드를 줄인다.
	# isJmp 플래그는 간접 jmp 호출의 존재 여부를 저장한다.
	# 존재하는 경우에 사용되는 것은 전역 변수들인 indirectStart(간접 jmp 호출의 시작 주소), endOfCode(코드 영역의 종료 주소)이다.
	startOfCode = 0
	endOfCode = 0
	forSize = re.findall(r'[0-9A-F]+', forJmp, re.I)
	codeSize = forSize[0]
	startOfCode = int(imgbase, 16) + int("1000", 16)
	endOfCode = int(imgbase, 16) + int("1000", 16) + int(codeSize, 16)

	firstAdd = str(hex(startOfCode))
	secondAdd = str(hex(endOfCode))

	newstdout.truncate(0)
	newstdout.seek(0)

	child.sendline('s ' + firstAdd + ' ' + secondAdd + ' ff 25')
	child.expect('0:000> ')
	res = newstdout.getvalue()
	indirectStart = 0

	firstline = res.splitlines()[0]
	secondline = ""

	for searchRes in res.splitlines():
		if searchRes == '0:000> ':
			break

		secondline = searchRes

		if int(firstline[:8], 16) + 6 != int(secondline[:8], 16):
			firstline = secondline
		else:
			indirectStart = int(firstline[:8], 16)
			break

	isJmp = 0

	if indirectStart != "":
		isJmp = 1

	newstdout.truncate(0)
	newstdout.seek(0)




"""
디스어셈블리 패널을 위한 함수. 
두 곳에서 사용되는데 한나는 t 같은 일반 제어 명령들과 ,v 자체 명령어이다. 이것은 IP 레지스터가 바뀌었다는 가정 하에 실행된다.
다른 한 곳은 ",vs <address>" 자체 명령어이다. 이것은 IP 레지스터가 바뀌지 않았다는 가정 하에 실행된다.
여부는 isinternal 변수로 구분한다.
"""
def asmview(preins, isinternal, adres):

	global firstAddress
	global secondAddress
	global neweip
	global addresses

	global indirectStart
	global endOfCode

	panelDis.delete(1.0, END)
	panelApi.delete(1.0, END)
	newstdout.truncate(0)
	newstdout.seek(0)


	# ,vs 명령어에서 사용되는 경우 ip 레지스터를 바꾸지 않고 가상으로 인자로 받은 주소를 IP 어드레스로 여기고 수행한다.
	if isinternal == 0:
		neweip = adres

	# 명령어들을 최대한 붙여쓰는 이유는 winpexpect를 통한 sendline, expect 사용 시마다 오버헤드가 크기 때문이다.
	ins = "ub " + neweip + " l9;.printf \"<>\";" + "u " + neweip + " l14"
	child.sendline(ins)
	child.expect('0:000> ')
	disResult = newstdout.getvalue()

	if disResult.find('Unable to') == -1:

		ubHalf = disResult.find('<>')
		# ubResult는 ub 명령어의 결과이다.
		ubResult = disResult[:ubHalf-1]
		# uResult는 u 명령어의 결과이다.
		uResult = disResult[ubHalf+2:]

		# firstAddress는 ,vs 명령어에서 사용될 때 다음 페이지를 구분하기 위해 이용된다.
		resultLN = ubResult.find('\n')
	
		firstAddress = ubResult[resultLN+1:resultLN+9]

		# 먼저 ub의 결과를 view 변수에 저장한다.
		view = ubResult[resultLN+1:ubHalf-1] + "\n"

	else:
	# ub 명령어의 경우 깨지면 제대로 나오지 않는 경향이 있다. 주로 안티디버깅 기법이 적용된 경우에 해당한다.
		ins = "u " + neweip + " l14"
		child.sendline(ins)
		child.expect('0:000> ')
		disResult = newstdout.getvalue()

		resultLN = disResult.find('\n')
		uResult = disResult[resultLN+1:]

		if isinternal == 0:
			firstAddress = disResult[resultLN+1:resultLN+9]

		view = ""


	newstdout.truncate(0)
	newstdout.seek(0)


	# 다음은 u의 결과를 view 변수에 저장함으로써 ub 뒤에 붙이는 방식이다.
	# 다음을 보면 알겠지만 ,vs 명령어에서 사용되는 방식과 그냥에서 사용되는 방식이 다르다.
	# ,vs에서 사용되는 경우는 그냥 붙이면 되지만 [ ub결과 + u결과 ]
	# IP 레지스터가 바뀌는 t 같은 명령에서는 현재 행이 추가적인 정보를 담고 있으므로 [ ub결과 + 현재행 + u결과 ] 형태로 만든다.
	# 현재 행은 인자로 받은 preins 변수이다.
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


	i = 10
	# 이제 view 변수를 보면 기본적인 사항은 끝났다. 대신 여기서는 disassembler에 API 이름 추가 같은 부가적인 기능을 구현한다.
	for line in view.splitlines():
	# 각 라인을 읽은 후에 다음을 수행한다.

		if line == '0:000> ':
		# 마지막이면 루프를 종료한다.
			break

		i = i+1
		addresses[i] = line[:8]

		# 매번 secondAddress를 저장하는데 마지막 라인이어서 루프가 끝나면 결국 마지막 주소가 secondAddress가 된다.
		# 이 변수는 이후에 ,vs 명령어에서 다음 페이지를 보여줄 때 사용된다.
		secondAddress = line[:8]

		newstdout.truncate(0)
		newstdout.seek(0)
		isCallExist = line.find("call")
		callAddress = extract(line)

		if isCallExist != -1 and callAddress != -1:
		# 만약 call 문자열이 존재하고, call에서 사용되는 주소 즉 괄호에서 주소를 얻은 경우 다음을 실행한다.
		# 예를들면 "FF15", "E8" 모두 사용 가능.
			
			sym = callAddress

			if iatStart <= int(callAddress, 16) <= iatEnd:
			# 직접 호출의 경우 해당 주소는 이미 IAT 영역에 존재하므로 다음을 수행한다.

				apilist = apifunc(sym)
				newstdout.truncate(0)
				newstdout.seek(0)
				apilist = apilist[:-7]
				line = str(i) + " " + line +'\t' + apilist + '\n'
				panelDis.insert(END, line)

				apiFirst = panelDis.search(apilist, "1.0", END)
				apiEnd = panelDis.search('\n', apiFirst, END)
				panelDis.tag_add("two", apiFirst, apiEnd)
				panelDis.tag_config("two", foreground="blue")

				# API 패널에 보여주기.
				apiPanelView(apilist)

				continue

			elif isJmp == 1 and indirectStart <= int(callAddress, 16) <= endOfCode:
			# jmp를 이용한 간접 호출의 경우 다음과 같이 추가적인 내용을 더 수행한다.
			# 예를들면 디버그 모드에서 컴파일할 때 볼 수 있는 "FF25" 명령어.

				indirect = apifunc(sym)
				newstdout.truncate(0)
				newstdout.seek(0)
				if indirect[4:8] == "25ff":
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
					line = str(i) + " " + line +'\t' + apilist + '\n'
					panelDis.insert(END, line)

					# API 패널에 보여주기.
					apiPanelView(apilist)

					apiFirst = panelDis.search(apilist, "1.0", END)
					apiEnd = panelDis.search('\n', apiFirst, END)
					panelDis.tag_add("two", apiFirst, apiEnd)
					panelDis.tag_config("two", foreground="blue")

					continue

			# 위의 두 영역에 포함되지 않는 경우에는 아무런 행위를 하지 않음으로써 오버헤드를 줄인다.


		line = str(i) + " " + line + '\n'
		panelDis.insert(END, line)


	# IP 레지스터 즉 현재 라인을 빨간색으로 표시한다.
	if isinternal == 1:
		first = "1.0"
		while True:
			eipfirst = panelDis.search(neweip, first, END)
			if not eipfirst:
				break
			eipend = panelDis.search('\n', eipfirst, END)
			panelDis.tag_add("one", eipfirst, eipend)
			panelDis.tag_config("one", foreground="red")
			first = eipend

	newstdout.truncate(0)
	newstdout.seek(0)




"""
왼쪽 디스어셈블리, 레지스터, 스택 창을 보여주는 함수.
일반적으로 t나 p 같은 제어 명령어를 사용하면 세 곳이 모두 업데이트된다.
참고로 디스어셈블리 창은 내부적으로 위에 정의된 asmview() 함수를 사용한다.
"""
def outview():
	global oldregister
	global neweip
	global premodule
	global nowmodule



	####
	####    Register    ####
	####
	newstdout.truncate(0)
	newstdout.seek(0)

	# 명령어들을 최대한 붙여쓰는 이유는 winpexpect를 통한 sendline, expect 사용 시마다 오버헤드가 크기 때문이다.
	child.sendline('r;  .printf "<>1";    .printf "eax ";da @eax; .printf "ebx "; da @ebx; .printf "ecx "; da @ecx; .printf "edx "; da @edx; .printf "esi "; da @esi; .printf "edi "; da @edi;  .printf "<>2";    dds esp l24;  .printf "<>3";  dda @esp l24')
	child.expect('0:000> ')
	inpResult = newstdout.getvalue()

	regResultHalf = inpResult.find('<>1')
	dResultHalf = inpResult.find('<>2')
	stackResultHalf = inpResult.find('<>3')
	inpResultEnd = inpResult.find('0:000> ')

	rResult = inpResult[:regResultHalf-1]
	dResult = inpResult[regResultHalf+3:dResultHalf-1]
	stackResult1 = inpResult[dResultHalf+3:stackResultHalf-1]
	stackResult2 = inpResult[stackResultHalf+3:inpResultEnd-1]

	newregister = { 'eax' : rResult[4:12], 'ebx' : rResult[17:26], 'ecx' : rResult[30:38], 'edx' : rResult[43:52], 'esi' : rResult[56:64], 'edi' : rResult[69:77], 
			 		'eip' : rResult[82:90], 'esp' : rResult[95:103], 'ebp' : rResult[108:116], 'efl' : rResult[225:233] }
	registerval = [1, 1, 1, 1, 1, 1]


	# da @register 명령어를 이용해서 레지스터 값에 해당하는 문자열을 보여준다.
	for line in dResult.splitlines():
		if line.split()[0] == 'eax':
			if line.find('??')>0:
				registerval[0] = ""
			else :
				registerval[0] = line[13:]
		elif line.split()[0] == 'ebx':
			if line.find('??')>0:
				registerval[1] = ""
			else :
				registerval[1] = line[13:]
		elif line.split()[0] == 'ecx':
			if line.find('??')>0:
				registerval[2] = ""
			else :
				registerval[2] = line[13:]
		elif line.split()[0] == 'edx':
			if line.find('??')>0:
				registerval[3] = ""
			else :
				registerval[3] = line[13:]
		elif line.split()[0] == 'esi':
			if line.find('??')>0:
				registerval[4] = ""
			else :
				registerval[4] = line[13:]
		elif line.split()[0] == 'edi':
			if line.find('??')>0:
				registerval[5] = ""
			else :
				registerval[5] = line[13:]


	# 정리해서 레지스터 창에 쓰기
	view = 'eax = ' + newregister['eax'] + registerval[0] + "\n"
	view = view + 'ecx = ' + newregister['ecx'] + registerval[2] + "\n"
	view = view + 'esi = ' + newregister['esi'] + registerval[4] + "\n"
	view = view + 'eip = ' + newregister['eip'] + "\n"
	view = view + 'ebp = ' + newregister['ebp'] + "\n"

	view2 = 'ebx = ' + newregister['ebx'] + registerval[1] + "\n"
	view2 = view2 + 'edx = ' + newregister['edx'] + registerval[3] + "\n"
	view2 = view2 + 'edi = ' + newregister['edi'] + registerval[5] + "\n"
	view2 = view2 + 'esp = ' + newregister['esp'] + "\n"
	view2 = view2 + 'efl = ' + newregister['efl'] + "\n"
	view2 = view2 + rResult[132:155]

	panelDis.delete(1.0, END)
	panelReg1.delete(1.0, END)
	panelReg2.delete(1.0, END)
	panelStack.delete(1.0, END)

	panelReg1.insert(END, view)
	panelReg2.insert(END, view2)


	# 변경된 레지스터 파란색으로 표시
	for key in oldregister:
		if oldregister[key] != newregister[key]:
			if key == 'eax':
				panelReg1.tag_add("eax", "1.6", "1.14")
				panelReg1.tag_config("eax", foreground="blue")
			elif key == 'ebx':
				panelReg2.tag_add("ebx", "1.6", "1.14")
				panelReg2.tag_config("ebx", foreground="blue")
			elif key == 'ecx':
				panelReg1.tag_add("ecx", "2.6", "2.14")
				panelReg1.tag_config("ecx", foreground="blue")
			elif key == 'edx':
				panelReg2.tag_add("edx", "2.6", "2.14")
				panelReg2.tag_config("edx", foreground="blue")
			elif key == 'esi':
				panelReg1.tag_add("esi", "3.6", "3.14")
				panelReg1.tag_config("esi", foreground="blue")
			elif key == 'edi':
				panelReg2.tag_add("edi", "3.6", "3.14")
				panelReg2.tag_config("edi", foreground="blue")
			elif key == 'eip':
				panelReg1.tag_add("eip", "4.6", "4.14")
				panelReg1.tag_config("eip", foreground="blue")
			elif key == 'esp':
				panelReg2.tag_add("esp", "4.6", "4.14")
				panelReg2.tag_config("esp", foreground="blue")
			elif key == 'ebp':
				panelReg1.tag_add("ebp", "5.6", "5.14")
				panelReg1.tag_config("ebp", foreground="blue")
			elif key == 'efl':
				panelReg2.tag_add("efl", "5.6", "5.14")
				panelReg2.tag_config("efl", foreground="blue")


	oldregister = newregister



	####
	####    Disassembly & etc    ####
	####

	# 현재 명령어 라인을 preins 변수로 미리 저장해 놓는다.
	# 또한 동시에 현재 모듈 이름을 nowmodule 변수에 저장해 놓는다.
	preins = ""
	counts = 0
	for line in rResult.splitlines():
		if counts == 3:
			nowmodule = re.split(r"[\+\!]", line)[0]
		elif counts == 4:
			preins = line
		counts = counts+1
	newstdout.truncate(0)
	newstdout.seek(0)

	# 이전 모듈과 현재 모듈이 다르다면 findiat()를 호출한다.
	if premodule != nowmodule:
		findiat()
		premodule = nowmodule

	# 아래는 디스어셈블리 창을 보여주는 asmview()를 호출하는 부분이다.
	# 받는 인자로는 현재 명령어 라인(굳이 따로 설정하는 이유는 windbg의 경우 현재 명령어 라인에서만 제공해주는 정보가 있기 때문이다. api 명이나 분기 여부 등),
	# outview()에서 호출되었는지 여부(이 경우에는 1이다)가 있다.
	neweip = newregister['eip']
	isinternal = 1
	asmview(preins, isinternal, "")



	####
	####    Stack    ####
	####
	# 기본적으로 "dds esp" 명령어에 "dda @esp" 명령어의 결과물을 붙여서 내놓는다.
	newstackResult = ""
	for line, line2 in zip(stackResult1.splitlines(), stackResult2.splitlines()):
		line = line + "\t\t\t" + line2[18:]
		newstackResult = newstackResult + line + "\n"

	view2 = newstackResult + "\n"
	panelStack.insert(END, view2)

	newstdout.truncate(0)
	newstdout.seek(0)




"""
명령어 입력과 관련된 콜백 함수로서 각종 명령어들을 받아들이고 처리한다.
제어 t, p, g 등의 명령어들은 outview()를 통한 업데이트를 수행하고,
나머지 기타 명령어들은 텍스트 창에 결과를 보여준다.
마지막으로 직접 구현한 자체 명령어들도 따로 정의하였다.
"""
def func(event):
	global old_inp
	global neweip
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
	if firstinp == 't' or firstinp == 'p' or firstinp == 'g' or firstinp == 'wt' or firstinp == 'ta' or firstinp == 'pa' or firstinp == 'tc' or firstinp == 'pc' or firstinp == 'tt' or firstinp == 'pt' or firstinp == 'tct' or firstinp == 'pct' or firstinp == 'th' or firstinp == 'ph' or firstinp == 'gc' or firstinp == 'gu' or firstinp == 'gh' or firstinp == 'gn' :
	# 제어 명령어인 경우 입력한다.
		child.sendline(inp)
		isEnd = child.expect(['0:000> ', 'Press any key to continue . . . '])
		if isEnd == 0:
		# 일반적으로 프롬프트가 나오는 경우.
			tpResult = newstdout.getvalue()
			if tpResult[:3] == 'eax':
			# 결과를 비교하여 일반적인 경우라면 오른쪽 화면에 입력한 명령어 및 프롬프트를 보여준다.
				panelCommand.config(state=NORMAL)
				panelCommand.insert(END, inp)
				panelCommand.insert(END, '\n')
				panelCommand.insert(END, '0:000> ')
				panelCommand.config(state=DISABLED)
			else:
			# 예외 발생 등 결과가 다른 경우 추가적인 메시지를 오른쪽 화면에 보여준다.
				panelCommand.config(state=NORMAL)
				panelCommand.insert(END, inp)
				panelCommand.insert(END, "\n")
				panelCommand.insert(END, tpResult.splitlines()[0])
				panelCommand.insert(END, "\n")
				panelCommand.insert(END, '0:000> ')
				panelCommand.config(state=DISABLED)
			# outview() 함수를 실행해 왼쪽 화면을 업데이트한다.
			outview()

		elif isEnd == 1:
		# 위의 명령어 시행 시 종료되어 "Press any key ..."가 나오는 경우.
			tpResult = newstdout.getvalue()
			child.sendline('\r')
			child.expect('0:000> ')
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, "\n")
			panelCommand.insert(END, "End")
			panelCommand.insert(END, "\n")
			panelCommand.insert(END, tpResult)
			panelCommand.insert(END, "\n")
			panelCommand.insert(END, '0:000> ')
			panelCommand.config(state=DISABLED)
			
			# 에러 때문에 한 번 더 먹어야 한다.
			child.expect('0:000> ')
			tpResult = newstdout.getvalue()
			#outview()


	#
	# 종료 명령어
	elif firstinp == 'q':
	# q 명령어를 사용한 경우 자체적으로 종료시킨다.
		child.close()
		root.destroy()


	#
	# 다음은 자체 명령어들이다.
	elif firstinp[0] == ',':
		if firstinp == ',bp':
		# 왼쪽의 번호를 이용한 방식. 주소 대신 줄 번호를 인자로 받는다.
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '0:000> ')
			panelCommand.config(state=DISABLED)
			num = int(inp[4:6])
			inp = "bp " + addresses.get(num)
			child.sendline(inp)
			child.expect('0:000> ')

		if firstinp == ',wt':
		# wt 명령도 간단하게 사용하게 하기 위해 자체 명령어를 만든 후 주소 대신 라인 번호를 입력받게 하였다.
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')

			num = int(inp[4:6])
			inp = firstinp[1:] + " " + addresses.get(num)
			child.sendline(inp)
			child.expect('0:000> ')

			panelCommand.insert(END, newstdout.getvalue())
			panelCommand.insert(END, '\n')			

			panelCommand.insert(END, '0:000> ')
			panelCommand.config(state=DISABLED)
			outview()

		elif firstinp == ',api':
		# API 이름을 인자로 넣으면 API 패널에서 클릭한 것과 같이 해당 api 함수에 대한 도움말을 보여준다.
			param = inp.split()[1]
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, '0:000> ')
			panelCommand.config(state=DISABLED)
			commands = ".shell -x C:\\" + "\"Program Files (x86)\"" + "\\\"Microsoft Help Viewer\"" + "\\v2.2\\HlpViewer.exe /catalogName VisualStudio14 /helpQuery \"method=f1&query=" + param + "\""
			child.sendline(commands)
			child.expect('0:000> ')

		elif firstinp == ',v':
		# 어지간한 경우에 자동으로 왼쪽 창들을 업데이트 시키지만 그렇지 않는 경우도 존재한다.
		# 예를들면 직접 ip 레지스터를 수정하는 경우가 그렇다. 이 경우에는 이 명령어를 사용하여 왼쪽 창을 업데이트시킨다.
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
			panelCommand.insert(END, '0:000> ')
			panelCommand.config(state=DISABLED)

		elif firstinp == ',vs':
		# 왼쪽 창의 디스어셈블리 창에서 ",vs <address>" 처럼 인자로 받은 주소를 기준으로 디스어셈블리를 보여준다.
		# 그냥 u 명령어를 사용해 오른쪽 창에서 봐도 되지만 굳이 이 자체 명령어를 만든 이유는
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


	#
	# 다음은 기타 명령어들로서 오른쪽 텍스트 창에만 결과를 보여준다.
	else:
		child.sendline(inp)
		isEnd = child.expect(['0:000> ', 'Hit Enter...'])
		if isEnd == 0:
		# 일반적으로 프롬프트가 나오는 경우
			line = newstdout.getvalue()	
			panelCommand.config(state=NORMAL)
			panelCommand.insert(END, inp)
			panelCommand.insert(END, '\n')
			panelCommand.insert(END, line)
			panelCommand.config(state=DISABLED)

		else:
		# "Hit Enter..." 라는 문자가 나오는 경우.
			line = newstdout.getvalue()

			while isEnd != 0:
				newstdout.truncate(0)
				newstdout.seek(0)
				child.sendline()
				isEnd = child.expect(['0:000> ', 'Hit Enter...'])
				line = line + newstdout.getvalue()

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

	# 기본 변수들.
	global premodule
	global nowmodule
	global iatEnd
	global iatStart


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
	frame1 = Frame(frame, height=50, width=110)
	frame1.grid(row=0, column=0, sticky=W+N)
	# panelDis는 디스어셈블리 패널이다.
	panelDis = Text(frame1, height=30, width=110)
	panelDis.grid(row=8, column=0, sticky=W+S)
	# panelReg1은 왼쪽 레지스터 패널이다.
	panelReg1 = Text(frame1, height=7, width=55)
	panelReg1.grid(row=0, column=0, sticky=W+N)
	# panelReg2는 오른쪽 레지스터 패널이다.
	panelReg2 = Text(frame1, height=7, width=55)
	panelReg2.grid(row=0, column=0, sticky=E+N)
	# panelStack은 스택 패널이다.
	panelStack = Text(frame1, height=12, width=110)
	panelStack.grid(row=33, column=0, sticky=W+N)

	# frame2는 오른쪽 화면을 의미한다.
	frame2 = Frame(frame, height=50, width=70)
	frame2.grid(row=0, column=110, sticky=W+N)
	# panelCommand는 명령어 결과를 보여주는 패널이다.
	panelCommand = Text(frame2, height=47, width=70)
	panelCommand.grid(row=0, column=110, sticky=W+N)
	# panelApi는 명령어 패널 아래에 위치한 패널로서 디스어셈블리 패널에서 보이는 API 함수들을 보여준다.
	# 해당 API 이름을 클릭하면 도움말 파일을 이용해 API 정보를 볼 수 있다.
	panelApi = Text(frame2, height=3, width=70)
	panelApi.grid(row=0, column=110, sticky=W+S)


	# winpexpect를 이용해 cdb의 입출력을 관리한다.
	# 먼저 cmd를 켜고 chcp로 언어를 영어로 설정한다. 
	# winpexpect에서 유니코드를 지원하지 않는데 종료 등의 경우 한글로 결과가 나오기 때문이다.
	#
	# 다음은 cdb를 이용한 초기 명령어이다. 바이너리를 오픈한 후 EP에 bp를 설치하고 실행한다.
	# > cdb [바이너리 이름]
	# 0:000> bp $exentry
	# 0:000> g
	#
	firstCommand = "cmd"
	cdbCommand = "cdb " + arg1
	
	child = winpexpect.winspawn(firstCommand)
	oldstdout = sys.stdout
	newstdout = io.StringIO()
	sys.stdout = newstdout
	child.logfile_read = sys.stdout

	child.expect('>')
	child.sendline('chcp 437')
	child.expect('>')
	child.sendline(cdbCommand)
	child.expect('0:000> ')
	child.sendline('bp $exentry')
	child.expect('0:000> ')
	child.sendline('g')
	child.expect('0:000> ')
	newstdout.truncate(0)
	newstdout.seek(0)

	panelCommand.config(state=NORMAL)
	panelCommand.insert(END, '0:000> ')
	panelCommand.config(state=DISABLED)

	# 모듈 및 iat 관련 변수들을 초기화한다.
	# 이후 outview() 함수에서부터 사용되며 이 함수는 초기 화면을 보여준다.
	premodule = ""
	nowmodule = ""
	iatStart = 0
	iatEnd = 0
	outview()
	newstdout.truncate(0)
	newstdout.seek(0)


	# 입력 받은 명령어를 변수 vari에 저장한 후 func 함수를 통해 콜백 형식으로 사용된다.
	vari = StringVar()
	E5 = Entry(frame2, textvariable=vari)
	E5.grid(row=48, column=110, sticky=N)
	E5.bind('<Return>', func)
	
	root.mainloop()
	child.close()

