1. install nodejs
1. `npm install bower`
1. make new virtualenv and activate it
1. make new sub-directory and chdir into it  
1. `git clone https://github.com/dblackdblack/tictactoe.git .`
1. `pip install -r requirements.txt`  
1. `bower install`
1. ```export TICTACTOE_ROOT=`pwd` ```
1. `python -c "import tictactoe ; tictactoe.db.create_all()"`
1. `uwsgi --emperor uwsgi.ini`
1. visit http://localhost:5000 in your browser
1. click on 'new user'
1. add a new user
1. enjoy!