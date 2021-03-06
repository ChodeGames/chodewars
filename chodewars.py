import tornado.ioloop
import tornado.web
import tornado.auth
import tornado.escape
import os.path
import logging
import datetime
import sys
import argparse

from tornado.options import define,options
from chodewars.game import Game
from chodewars.player import Player
from chodewars.planet import Planet

define("port", default=9000, help="run on the given port", type=int)

version = "0.0"

game = None

class Application(tornado.web.Application):
  def __init__(self):
    handlers=[
      (r"/", MainHandler),
      (r"/login", LoginHandler),
      (r"/logout", LogoutHandler),
      (r"/add/([\w]*)", AddHandler),
      (r"/c/([\w]*)/", CommandHandler),
    ]
    
    settings = dict(
      template_path = os.path.join(os.path.dirname(__file__), "templates"),
      static_path = os.path.join(os.path.dirname(__file__), "static"),
      cookie_secret = "43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
      login_url = "/login",
      debug = True,
    )
    tornado.web.Application.__init__(self,handlers,**settings)

class BaseHandler(tornado.web.RequestHandler):
  def get_current_user(self):
    user_json = self.get_secure_cookie("user")
    """user_json is of the form:
    {u'email': u'matthew.parlette@gmail.com',
    u'first_name': u'Matthew',
    u'last_name': u'Parlette',
    u'claimed_id': u'https://www.google.com/accounts/o8/id?id=AItOawn5BtKjHuaIP870Gex-U3jwWKLi2X2pqGw',
    u'name': u'Matthew Parlette'}"""
    if not user_json: return None
    return tornado.escape.json_decode(user_json)
  
  def get_current_player(self):
    if not self.current_user: return None
    if not game: return None
    if 'email' in self.current_user:
      return game.get_player_by_id(self.current_user['email'])
    else:
      #If email doesn't exist in the cookie, then it needs to be refreshed
      self.clear_cookie('user')
      self.redirect("/")
    return None

class MainHandler(BaseHandler):
  @tornado.web.authenticated
  def get(self):
    player = self.get_current_player()
    if not player:
      self.redirect("/add/player")
    
    ship = game.get_parent(player) if player else None
    if player: print "player loaded as %s" % str(player.to_dict())
    if ship: print "ship loaded as %s" % str(ship.to_dict())
    render_location = game.get_parent(ship) if ship else None
    
    #for line in game.visualize_cluster(player):
      #print "%s\n" % line
    
    self.render(
      "index.html",
      page_title = "chodewars",
      header_text = "Heading",
      footer_text = "Chodewars",
      user = self.current_user,
      player = player,
      ship = ship,
      render_location = render_location,
      game = game,
    )

class LoginHandler(BaseHandler, tornado.auth.GoogleMixin):
  @tornado.web.asynchronous
  def get(self):
    if self.get_argument("openid.mode", None):
      self.get_authenticated_user(self.async_callback(self._on_auth))
      return
    self.authenticate_redirect(ax_attrs=["name","email"])

  def _on_auth(self, user):
    if not user:
      raise tornado.web.HTTPError(500, "Google auth failed")
    self.set_secure_cookie("user", tornado.escape.json_encode(user))
    self.redirect("/")

class LogoutHandler(BaseHandler):
  def get(self):
    self.clear_cookie("user")
    self.write("You are now logged out")

class AddHandler(BaseHandler):
  #@tornado.web.authenticated
  def get(self,add_type):
    self.render(
      "add.html",
      page_title = "Create Player",
      header_text = "Create",
      footer_text = "Chodewars",
      user = self.current_user,
      add_type = add_type,
    )
  
  def post(self,add_type):
    if game:
      if add_type == "player":
        name = self.get_argument('name','')
        print "Creating new player %s..." % name
        if game.add_player(Player(initial_state = {'id':self.current_user['email'],'name':name})):
          print "Player %s created" % name
          planet_name = self.get_argument('planet_name',None)
          ship_name = self.get_argument('ship_name',None)
          if planet_name and ship_name:
            player = self.get_current_player()
            print "Creating home sector..."
            if game.assign_home_sector(player,planet_name,ship_name):
              print "...ok"
            else:
              print "Error assigning home sector for %s" % str(player)
          else:
            print "planet_name or ship_name was not received, nothing was created for this player"
        else:
          print "Error creating player %s" % name
    else:
      print "Game is not initialized!"
        
    self.redirect("/")

class CommandHandler(BaseHandler):
  def get(self,command):
    print "cmd: %s" % str(command)
    player = self.get_current_player()
    if game:
      if command == "move":
        print "\n\n---------------------"
        sector_id = self.get_argument("sector",default = None, strip = True)
        if sector_id:
          sector = game.load_object_by_id(sector_id)
          print "sector loaded as %s" % str(sector)
          if sector:
            print "Moving player"
            game.move_ship(game.get_parent(player),sector)
      if command in ("land"):
        target_id = self.get_argument("target",default = None, strip = True)
        if target_id:
          target = game.load_object_by_id(target_id)
          if target:
            print "Landing on %s" % str(target)
            game.move_ship(game.get_parent(player),target)
      if command in ("takeoff"):
        ship = game.get_parent(player)
        current_ship_location = game.get_parent(ship)
        if current_ship_location.type in ("Planet"):
          game.move_ship(ship,game.get_parent(current_ship_location))
    else:
      self.write("Game not initialized")
    
    self.redirect("/")
  
  def post(self,command,argument):
    pass

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Process command line options.')
  parser.add_argument('--bigbang', action='store_true', help='Execute a Big Bang, this deletes an existing universe and creates a new one.')
  parser.add_argument('--version', action='version', version='Chodewars v'+version)
  args = parser.parse_args()
  
  print "Creating game object..."
  game = Game()
  if game:
    print "...ok"
  else:
    print "error initializing game"
    sys.exit(1)
  
  if args.bigbang:
    print "Executing Big Bang..."
    game.big_bang()
    print "...ok"
    sys.exit(0)
  
  print "Game created, listening for connections..."
  app = Application()
  app.listen(options.port)
  tornado.ioloop.IOLoop.instance().start()
