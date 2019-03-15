from flask import Flask, request, render_template, url_for, redirect, flash, jsonify,Markup
import flask_login
from pymongo import MongoClient
from passlib.hash import sha256_crypt
import requests
from os import urandom,remove
from binascii import hexlify

from config import MONGODB_URI, db_name, SECRET_KEY

client = MongoClient(MONGODB_URI)
db = client.get_database(db_name)
users = db.User
ide=db.Codes
homecodes= db.home

languages={"ada":53,"android":47,"android_gradle":63,"babeljs":65,"bash":14,"brainfuck":19,"c":1,"c_clang":67,"clojure":13,
"cobol":36,"coffeescript":59,"cpp":2,"cpp14":58,"cpp_clang":68,"csharp":9,"d":22,"db2":44,"elixir":52,"erlang":16,"fortran":54,
"fsharp":33,"go":21,"groovy":31,"haskell":12,"haxe":69,"java":3,"java8":43,"javascript":20,"julia":57,"kotlin":71,"lolcode":38,"lua":18,
"maven":45,"mysql":10,"node":64,"objectivec":32,"ocaml":23,"octave":46,"oracle":11,"pascal":25,"perl":6,"php":7,"pypy":61,"pypy3":62,
"python":5,"python3":30,"r":24,"racket":49,"ruby":8,"rust":50,"sbcl":26,"sbt":70,"scala":15,"smalltalk":39,"swift":51,"tcl":40,"text":28,
"text_pseudo":7,"tsql":42,"typescript":66,"visualbasic":37,"whitespace":41,"xquery":48}


app=Flask(__name__)
app.secret_key= SECRET_KEY

login_manager=flask_login.LoginManager()
login_manager.init_app(app)


class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(email):
	d=users.find_one({"username":email})
	if d is None:
		return
	user = User()
	user.id = email
	return user


@login_manager.request_loader
def request_loader(request):
    email = request.form.get('username')
    d=users.find_one({"username":email})
    if d is None:
        return
    user = User()
    user.id = email
    password=request.form.get('password')
    user.is_authenticated = sha256_crypt.verify(d['password'], password)
    return user


@app.route('/',methods=['GET','POST'])
def home():
	if flask_login.current_user.is_authenticated:
		return redirect(url_for("user_profile",user_id=str(flask_login.current_user.id)))
	if request.method=='GET':
		return render_template("home.html",languages=languages)
	elif request.method=='POST':
		code=request.form.get('code')
		language=request.form.get('lang')
		input_=request.form.get('testcase')
		if language=="-1":
			flash("Please enter language")
			return render_template("home.html",languages=languages)
		if input_ =="":
			input_=" "
		guest=hackerrank_api(code=code,language=language,input_=input_)
		flag=False
		if guest['result']=="Successfully Executed":
			flag=True
		homecodes.insert_one(guest)
		return render_template('home_submit.html',code=code,language=int(language),input=input_,output=guest['output'], \
			result=guest['result'],time=guest['time'],mem=guest['memory'],languages=languages,flag=flag)


@app.route('/register/',methods=['GET','POST'])
def register():
	if request.method=='GET':
		return render_template('register.html')
	elif request.method=='POST':
		new_user={}
		new_user['username']=request.form.get('username')
		if users.find_one({'Username':new_user['username']}):
			flash("Username already exists!")
			return redirect(url_for("register"))
		new_user['email']=request.form.get('email')
		pass1=request.form.get('password')
		if len(pass1)<8:
			flash("Password must be of 8 characters!")
			return redirect(url_for('register'))
		chk_pass=request.form.get("password_again")
		if pass1!=chk_pass:
			flash("Password mismatch.\nPlease register again.")
			return redirect(url_for('register'))
		new_user['password']=sha256_crypt.encrypt(pass1)
		new_user['key']=hexlify(urandom(24)).decode('utf-8')
		new_user['name']=request.form.get('name')
		new_user['age']=request.form.get('age')
		new_user['country']=request.form.get('country')
		users.insert_one(new_user)
		flash("Successfully registered and logged in!")
		user=User()
		user.id=new_user['username']
		flask_login.login_user(user)
		return redirect(url_for('user_profile',user_id=new_user['username']))
	return "None"


@app.route('/login/', methods=['GET', 'POST'])
def login():
	if request.method == 'GET':
		return render_template("login.html")
	username = request.form['username']
	password=request.form['password']
	d=users.find_one({"username":username})
	if d is None:
		flash("Invalid username\n")
		return redirect(url_for('login'))
	pass_chk=sha256_crypt.verify(password,d['password'])
	if pass_chk:
	    user = User()
	    user.id = username
	    flask_login.login_user(user)
	    return redirect(url_for('user_profile',user_id=username))
	flash("Bad login!\n Login again.")
	return redirect(url_for('login'))


@app.route('/users/<user_id>/')
@flask_login.login_required
def user_profile(user_id):
	d1=users.find_one({"username":flask_login.current_user.id})
	header=["S.No.","Title","Language","Result"]
	data=[]
	try:
		langs={}
		d=list(ide.find({"username":flask_login.current_user.id}))
		for i in range(len(d)):
			l_code=int(d[i].get('lang'))
			for l in languages.keys():
				if languages[l]==l_code:
					lang=l
					break
			if lang.capitalize() in langs.keys():
				langs[lang.capitalize()]+=1
			else:
				langs[lang.capitalize()]=1
			data.append([i+1,d[i].get("title"),lang.capitalize(),d[i].get('result')])
	except Exception as e:
		print(e)
	return render_template("user_profile.html",username=d1.get("username"),email=d1.get("email"),key=d1.get("key"),\
		header=header,data=data,age=d1.get("age"),country=d1.get("country"),name=d1.get('name'),values=langs.values(),labels=langs.keys())


@app.route('/users/<user_id>/edit/',methods=['GET','POST'])
def edit_details(user_id):
	if request.method=='GET':
		return render_template('edit_details.html',username=user_id)
	elif request.method=='POST':
		new_user={}
		pass1=request.form.get('password')
		if len(pass1)<8:
			flash("Password must be of 8 characters!")
			return redirect(url_for('edit_details'))
		chk_pass=request.form.get("password_again")
		if pass1!=chk_pass:
			flash("Password mismatch.\nPlease register again.")
			return redirect(url_for('edit_details'))
		new_user['password']=sha256_crypt.encrypt(pass1)
		new_user['name']=request.form.get('name')
		new_user['age']=request.form.get('age')
		new_user['country']=request.form.get('country')
		users.update_one({"username":user_id},{"$set":new_user})
		flash("Successfully updated!")
		return redirect(url_for('user_profile',user_id=user_id))
	return "None"

@app.route('/users/<user_id>/onlineide/',methods=['GET','POST'])
@flask_login.login_required
def onlineide(user_id):
	if request.method=="GET":
		return render_template("uploadcode.html",username= user_id,languages=languages)
	elif request.method=="POST":
		if request.form.get('_method')=="POST":
			username=str(flask_login.current_user.id)
			title=request.form.get("title")
			title2=title.replace("_","a")
			if not title2.isalnum():
				flash("Title must be of alphanumeric characters and underscore.")
				return render_template("uploadcode.html",username=username,languages=languages)
			existing_title=ide.find_one({"username":username,"title": title})
			if existing_title is not None:
				flash("Title must be unique.")
				return render_template("uploadcode.html",username=username,languages=languages)
			code=request.form.get("code")
			code1=request.files.get('code1')
			if code1 is not None:
				code1.save("static/{}".format(code1.filename))
				with open("static/{}".format(code1.filename)) as f:
					code=f.read()
				remove("static/{}".format(code1.filename))
			language=request.form.get("lang")
			input_=request.form.get('testcase')
			if language=="-1":
				flash("Please enter language")
				return render_template("uploadcode.html",languages=languages)
			if input_ =="":
				input_=" "
			member=hackerrank_api(username=username,title=title,code=code,language=language,input_=input_)
			flag=False
			if member['result']=="Successfully Executed":
				flag=True
			ide.insert_one(member)
			return render_template("submit.html",username=username,code=code,language=int(language),input=input_,output=member['output'], \
						result=member['result'],time=member['time'],mem=member['memory'],languages=languages,flag=flag,title=title)
		elif request.form.get("_method")=="PATCH":
			username=str(flask_login.current_user.id)
			title=request.form.get("title")
			title2=title.replace("_","a")
			if not title2.isalnum():
				flash("Title must be of alphanumeric characters and underscore.")
				return render_template("uploadcode.html",username=username,languages=languages)
			code=request.form.get("code")
			code1=request.files.get('code1')
			if code1 is not None:
				code1.save("static/{}".format(code1.filename))
				with open("static/{}".format(code1.filename)) as f:
					code=f.read()
				remove("static/{}".format(code1.filename))
			language=request.form.get("lang")
			input_=request.form.get('testcase')
			if language=="-1":
				flash("Please enter language")
				return render_template("uploadcode.html",languages=languages)
			if input_ =="":
				input_=" "
			member=hackerrank_api(username=username,title=title,code=code,language=language,input_=input_)
			flag=False
			if member['result']=="Successfully Executed":
				flag=True
			existing_title=ide.find_one({"username":username,"title": title})
			if existing_title is not None:
				ide.update_one({"username":username,"title":title},{"$set":member})
			else:
				ide.insert_one(member)
			return render_template("submit.html",username=username,code=code,language=int(language),input=input_,output=member['output'], \
						result=member['result'],time=member['time'],mem=member['memory'],languages=languages,flag=flag,title=title)


@app.route('/users/<user_id>/<title>/',methods=['GET','POST'])
@flask_login.login_required
def particular_code(user_id,title):
	if request.method=="GET":
		member=ide.find_one({"username":user_id,"title":title})
		flag=False
		if member['result']=="Successfully Executed":
			flag=True
		return render_template("particular_code.html",username=member['username'],code=member['code'],language=member['lang'],\
			input=member['input'],output=member['output'],result=member['result'],time=member['time'],mem=member['memory'],\
			languages=languages,flag=flag,title=member['title'])
	elif request.method=="POST":
		username=str(flask_login.current_user.id)
		title1=request.form.get("title")
		title2=title1.replace("_","a")
		if not title2.isalnum():
			flash("Title must be of alphanumeric characters and underscore.")
			return redirect(url_for("particular_code",user_id=username,title=title))
		title=title1
		code=request.form.get("code")
		code1=request.files.get('code1')
		if code1 is not None:
			code1.save("static/{}".format(code1.filename))
			with open("static/{}".format(code1.filename)) as f:
				code=f.read()
			remove("static/{}".format(code1.filename))
		language=request.form.get("lang")
		input_=request.form.get('testcase')
		if language=="-1":
			flash("Please enter language")
			return redirect(url_for("particular_code",user_id=username,title=title))
		if input_ =="":
			input_=" "
		member=hackerrank_api(username=username,title=title,code=code,language=language,input_=input_)
		flag=False
		if member['result']=="Successfully Executed":
			flag=True
		existing_title=ide.find_one({"username":username,"title": title})
		if existing_title is not None:
			ide.update_one({"username":username,"title":title},{"$set":member})
		else:
			ide.insert_one(member)
		return render_template("particular_code.html",username=username,code=code,language=int(language),input=input_,output=member['output'], \
					result=member['result'],time=member['time'],mem=member['memory'],languages=languages,flag=flag,title=title)


@app.route('/users/<user_id>/<title>/delete/',methods=['GET'])
@flask_login.login_required
def delete_code(user_id,title):
	ide.delete_one({"username":user_id,"title":title})
	return redirect(url_for("user_profile",user_id=user_id))

@app.route('/api/docs/')
def apidocs():
	if flask_login.current_user.is_authenticated:
		d=users.find_one({"username":str(flask_login.current_user.id)})
		return render_template("doc_loggedin.html",key=d['key'],username=d['username'])
	else:
		return render_template("doc_anonymous.html")

@app.route('/users/<user_id>/<title>/download/',methods=['GET'])
@flask_login.login_required
def download_code(user_id,title):
	code=ide.find_one({"username":user_id,"title":title})
	if code is None:
		return "None"
	return str(code['code'])


@app.route("/api/lang_codes/")
def lang_codes():
	lang_list=[]
	count=1
	for i in languages.keys():
		lang_list.append([count,i.capitalize(),languages[i]])
		count+=1
	flag=True
	username=None
	if flask_login.current_user.is_authenticated:
		d=users.find_one({"username":str(flask_login.current_user.id)})
		flag=False
		username=d['username']
	return render_template("lang_codes.html",data=lang_list,flag=flag)

@app.route("/api",methods=['GET','POST','PATCH','DELETE'])
def api():
	if (request.method=='GET'):
		key=request.args.get("key")
		if key is None:
			return jsonify({"error":"Key is required. Read the docs"}),404
		d=users.find_one({"key":key})
		if d is None:
			return jsonify({"error":"You are not registered."}),404
		username=d['username']
		title=request.args.get("title")
		if title is None:
			codes=list(ide.find({"username":username}))
			for code in codes:
				code.pop('_id')
			return json_util.dumps(codes),200
		code=ide.find_one({"username":username,"title":title})
		code.pop('_id')
		if code is None:
			return jsonify({"error":"No file with given title"})
		return json_util.dumps(code),200
	key=request.form.get("key")
	if key is None:
		return jsonify({"error":"Key is required. Read the docs"}),400
	d=users.find_one({"key":key})
	if d is None:
		return jsonify({"error":"You are not registered."}),400
	username=d['username']
	if request.method=='POST':
		title1=request.form.get("title")
		if title1 is None:
			return jsonify({"error":"No parameter with key title."}),400
		title2=title1.replace("_","a")
		if not title2.isalnum():
			return jsonify({"key":"Title must be of alphanumeric characters and underscore."}),400
		existing_title=ide.find_one({"username":username,"title": title})
		if existing_title is not None:
			return jsonify({"key":"Title must be unique."}),400
		title=title1
		code=request.form.get("code")
		language=request.form.get("lang")
		input_=request.form.get('input')
		if  language is None:
			return jsonify({"error":"Language is not given."}),400
		if input_ =="":
			input_=" "
		member=hackerrank_api(username=username,title=title,code=code,language=language,input_=input_)
		member1=dict(member)
		ide.insert_one(member1)
		return jsonify(member),200
	elif request.method=='PATCH':
		title_old=request.form.get("title1")
		if title_old is None:
			return jsonify({"error":"Title of existing file is required for updation. Read the docs."}),400
		code=ide.find_one({"username":username,"title":title_old})
		if code is None:
			return jsonify({"error":"No file with given title"})
		title1=request.form.get("title")
		if title1 is None:
			return jsonify({"error":"No parameter with key title."}),400
		title2=title1.replace("_","a")
		if not title2.isalnum():
			return jsonify({"key":"Title must be of alphanumeric characters and underscore."}),400
		existing_title=ide.find_one({"username":username,"title": title1})
		if existing_title is not None:
			return jsonify({"key":"Title must be unique."}),400
		title=title1
		code=request.form.get("code")
		language=request.form.get("lang")
		input_=request.form.get('input')
		if  language is None:
			return jsonify({"error":"Language is not given."}),400
		if input_ =="":
			input_=" "
		member=hackerrank_api(username=username,title=title,code=code,language=language,input_=input_)
		ide.update_one({"username":username,"title":title_old},{"$set":member})
		return jsonify(member),200
	elif request.method=='DELETE':
		title=request.form.get("title")
		if title is None:
			return jsonify({"error":"Title of existing file is required for deletion. Read the docs"}),400
		ide.delete_one({"username":username,"title":title})
		return jsonify({"result":"Successfully deleted."}),200

@app.route('/logout/')
def logout():
    flask_login.logout_user()
    flash("You have been successfully logged out!")
    return redirect(url_for("home"))

@login_manager.unauthorized_handler
def unauthorized_handler():
    flash('Unauthorized')
    return redirect(url_for("home"))

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.errorhandler(404)
def page_not_found(e):
	return render_template("404.html")

def hackerrank_api(username=None,title=None,code=None,language=None,input_=None):
	try:
		ip=[]
		input_=input_.replace('\r','')
		ip.append(input_)
		key="hackerrank|751319-994|d057e21968795c38201ca37d376201eff936f2b9"
		url="http://api.hackerrank.com/checker/submission.json"
		data={
		    'format':'json',
		    'source':code,
		    'lang':int(language),
		    'testcases':str(ip),
		    'api_key': key
		}
		r=requests.post(url,data=data)
		response=r.json()
		output=response['result']['compilemessage']
		result="Compilation Error"
		time=None
		mem=None
		#print(response)
		if not output:
			message=response['result']['message'][0]
			if message=="Success":
				result="Successfully Executed"
				output=response['result']['stdout'][0]
				time=response['result']['time'][0]
				mem=response['result']['memory'][0]
			elif message=="Runtime error":
				result="Runtime Error"
				output=response['result']['stderr'][0]
	except Exception as e:
		print(e)
		result="Unable to process your request. Please try again later. Sorry for inconvenience."
		output=None
		time=None
		mem=None
	O_IDE={}
	O_IDE['code']=code
	O_IDE['lang']=int(language)
	O_IDE['input']=input_
	O_IDE['output']=output
	O_IDE['result']=result
	O_IDE['time']=time
	O_IDE['memory']=mem
	if username is not None:
		#Authenticated User
		O_IDE['username']=username
		O_IDE['title']=title
	#print(O_IDE)
	return O_IDE


if __name__=="__main__":
	app.run(port=8000,debug=True,use_reloader=True)
