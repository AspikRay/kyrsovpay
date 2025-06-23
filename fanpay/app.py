from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fanpay.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    ads = db.relationship('Ad', backref='category', lazy=True)

class Ad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    currency = db.Column(db.String(8), default='RUB')

class PurchaseLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    ad_id = db.Column(db.Integer, db.ForeignKey('ad.id'), nullable=False)
    username = db.Column(db.String(80))
    ad_title = db.Column(db.String(120))
    price = db.Column(db.Float)
    currency = db.Column(db.String(8))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/set_currency', methods=['POST'])
def set_currency():
    currency = request.form.get('currency', 'RUB')
    session['currency'] = currency
    return redirect(request.referrer or url_for('index'))

@app.route("/")
def index():
    category_id = request.args.get('category', type=int)
    categories = Category.query.all()
    currency = session.get('currency', 'RUB')
    if category_id:
        ads = Ad.query.filter_by(category_id=category_id, is_approved=True).order_by(Ad.id.desc()).all()
    else:
        ads = Ad.query.filter_by(is_approved=True).order_by(Ad.id.desc()).all()
    return render_template("index.html", ads=ads, categories=categories, selected_category=category_id)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        errors = []
        if not username or not password:
            errors.append("Заполните все поля.")
        if len(username) < 3:
            errors.append("Логин слишком короткий.")
        if len(password) < 5:
            errors.append("Пароль слишком короткий.")
        if User.query.filter_by(username=username).first():
            errors.append("Пользователь уже существует.")
        if errors:
            for e in errors:
                flash(e)
            return redirect(url_for("register"))
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Регистрация успешна.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        errors = []
        if not username or not password:
            errors.append("Заполните все поля.")
        user = User.query.filter_by(username=username, password=password).first()
        if not user:
            errors.append("Неверные данные.")
        if errors:
            for e in errors:
                flash(e)
            return redirect(url_for("login"))
        session["user_id"] = user.id
        session["username"] = user.username
        session["is_admin"] = user.is_admin
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/create", methods=["GET", "POST"])
def create_ad():
    if "user_id" not in session:
        return redirect(url_for("login"))
    categories = Category.query.all()
    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form["description"].strip()
        price = request.form["price"].strip()
        category_id = request.form["category_id"].strip()
        errors = []
        if not title or not description or not price or not category_id:
            errors.append("Заполните все поля.")
        try:
            price_val = float(price)
            if price_val <= 0:
                errors.append("Цена должна быть положительной.")
        except ValueError:
            errors.append("Некорректная цена.")
        if errors:
            for e in errors:
                flash(e)
            return redirect(url_for("create_ad"))
        currency = request.form.get("currency", session.get('currency', 'RUB'))
        ad = Ad(title=title, description=description, price=price_val, user_id=session["user_id"], category_id=int(category_id), currency=currency, is_approved=False)
        db.session.add(ad)
        db.session.commit()
        flash("Объявление отправлено на модерацию.")
        return redirect(url_for("index"))
    return render_template("create_ad.html", categories=categories)

@app.route("/ad/<int:ad_id>")
def ad_detail(ad_id):
    ad = Ad.query.get_or_404(ad_id)
    return render_template("ad_detail.html", ad=ad)

@app.route("/admin")
def admin_panel():
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    users = User.query.all()
    ads = Ad.query.order_by(Ad.id.desc()).all()
    categories = Category.query.all()
    return render_template("admin.html", users=users, ads=ads, categories=categories)

@app.route("/admin/delete_ad/<int:ad_id>")
def delete_ad(ad_id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    ad = Ad.query.get_or_404(ad_id)
    db.session.delete(ad)
    db.session.commit()
    flash("Объявление удалено.")
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete_user/<int:user_id>")
def delete_user(user_id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash("Нельзя удалить администратора.")
    else:
        db.session.delete(user)
        db.session.commit()
        flash("Пользователь удалён.")
    return redirect(url_for("admin_panel"))

@app.route("/admin/add_category", methods=["POST"])
def add_category():
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    name = request.form["name"]
    if not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name))
        db.session.commit()
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete_category/<int:category_id>")
def delete_category(category_id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    category = Category.query.get_or_404(category_id)
    if category.ads:
        flash("Нельзя удалить категорию с объявлениями.")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Категория удалена.")
    return redirect(url_for("admin_panel"))

@app.route("/admin/approve_ad/<int:ad_id>")
def approve_ad(ad_id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    ad = Ad.query.get_or_404(ad_id)
    ad.is_approved = True
    db.session.commit()
    flash("Объявление одобрено.")
    return redirect(url_for("admin_panel"))

@app.route("/admin/edit_ad/<int:ad_id>", methods=["GET", "POST"])
def edit_ad(ad_id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    ad = Ad.query.get_or_404(ad_id)
    categories = Category.query.all()
    if request.method == "POST":
        ad.title = request.form["title"]
        ad.description = request.form["description"]
        ad.price = float(request.form["price"])
        ad.category_id = int(request.form["category_id"])
        ad.currency = request.form.get("currency", ad.currency)
        ad.is_approved = "is_approved" in request.form
        db.session.commit()
        flash("Объявление обновлено.")
        return redirect(url_for("admin_panel"))
    return render_template("edit_ad.html", ad=ad, categories=categories)

@app.route("/pay/<int:ad_id>", methods=["GET", "POST"])
def pay_ad(ad_id):
    ad = Ad.query.get_or_404(ad_id)
    if request.method == "POST":
        card_number = request.form.get("card_number", "").replace(" ", "")
        if not card_number.isdigit() or len(card_number) < 12:
            flash("Некорректный номер карты.")
            return redirect(url_for("pay_ad", ad_id=ad.id))
        log = PurchaseLog(
            user_id=session.get("user_id"),
            ad_id=ad.id,
            username=session.get("username"),
            ad_title=ad.title,
            price=ad.price,
            currency=ad.currency
        )
        db.session.add(log)
        db.session.delete(ad)
        db.session.commit()
        flash("Покупка успешно совершена! Товар удалён.")
        return redirect(url_for("index"))
    return render_template("pay.html", ad=ad)

@app.route("/admin/purchases")
def admin_purchases():
    if not session.get("is_admin"):
        return redirect(url_for("index"))
    logs = PurchaseLog.query.order_by(PurchaseLog.timestamp.desc()).all()
    return render_template("admin_purchases.html", logs=logs)

if __name__ == "__main__":
    with app.app_context():
        if not os.path.exists("fanpay.db"):
            db.create_all()
            # Добавим несколько категорий по умолчанию
            default_categories = ["Игры", "Аккаунты", "Валюта", "Услуги"]
            for name in default_categories:
                if not Category.query.filter_by(name=name).first():
                    db.session.add(Category(name=name))
            db.session.commit()
        
        # ✅ Проверка: админ уже есть?
        existing_admin = User.query.filter_by(username="Ramazan666gang").first()
        if not existing_admin:
            admin = User(username="Ramazan666gang", password="fliperziro131", is_admin=True)
            db.session.add(admin)
            db.session.commit()
            print("✅ Админ создан: admin / admin123")
        else:
            print("🔒 Админ уже существует.")
    
    app.run(debug=True)

