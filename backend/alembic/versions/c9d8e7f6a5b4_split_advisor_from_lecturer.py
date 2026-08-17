"""tach co van hoc tap khoi bang giang vien

Cố vấn học tập trước đây lưu trong bảng lecturer (mỗi cố vấn là 1 giảng viên
có tài khoản role "advisor"); migration này tách thành bảng advisor riêng:
  - tạo bảng advisor (code, name) + users.advisor_id
  - chuyển dữ liệu: lecturer nào đang là cố vấn (có user role advisor, hoặc
    được homeroom_class.advisor_id trỏ tới) → tạo bản ghi advisor tương ứng,
    trỏ lại users.advisor_id và homeroom_class.advisor_id, xóa hàng lecturer cũ
  - KHÔNG mất dữ liệu: chỉ di chuyển + trỏ lại FK

Chạy được cả Postgres (deploy Supabase) lẫn SQLite (local dev): Postgres dùng
ALTER trực tiếp với tên constraint chuẩn, SQLite dùng batch_alter_table.

Revision ID: c9d8e7f6a5b4
Revises: a1b2c3d4e5f6
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Naming convention để batch mode (SQLite) định danh được constraint vô danh
NAMING = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
}

# Lược đồ tối thiểu phục vụ di chuyển dữ liệu (SQLAlchemy Core — chạy trên mọi dialect)
advisor_t = sa.table(
    "advisor",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
)
lecturer_t = sa.table(
    "lecturer",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("department", sa.String),
)
users_t = sa.table(
    "users",
    sa.column("id", sa.Integer),
    sa.column("role", sa.String),
    sa.column("lecturer_id", sa.Integer),
    sa.column("advisor_id", sa.Integer),
)
homeroom_t = sa.table(
    "homeroom_class",
    sa.column("id", sa.Integer),
    sa.column("advisor_id", sa.Integer),
)
course_class_t = sa.table(
    "course_class",
    sa.column("lecturer_id", sa.Integer),
)


def _create_advisor_table() -> None:
    op.create_table(
        'advisor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_advisor_name', 'advisor', ['name'], unique=False)


def _drop_old_fks() -> None:
    """Bỏ FK homeroom_class.advisor_id→lecturer TRƯỚC khi trỏ lại giá trị về advisor.

    Lưu ý: users.lecturer_id→lecturer được GIỮ NGUYÊN — tài khoản giảng viên vẫn
    cần FK đó; chỉ có homeroom_class.advisor_id là đổi bảng tham chiếu.
    """
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.drop_constraint('homeroom_class_advisor_id_fkey', 'homeroom_class', type_='foreignkey')
    else:
        # SQLite: constraint vô danh — batch mode nhận diện theo naming convention
        with op.batch_alter_table('homeroom_class', naming_convention=NAMING, recreate='always') as b:
            b.drop_constraint('fk_homeroom_class_advisor_id_lecturer', type_='foreignkey')


def _add_new_fks() -> None:
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.create_foreign_key(
            'homeroom_class_advisor_id_fkey', 'homeroom_class', 'advisor',
            ['advisor_id'], ['id'],
        )
        op.create_foreign_key(
            'users_advisor_id_fkey', 'users', 'advisor', ['advisor_id'], ['id'],
        )
    else:
        with op.batch_alter_table('homeroom_class', naming_convention=NAMING, recreate='always') as b:
            b.create_foreign_key('fk_homeroom_class_advisor_id_advisor', 'advisor', ['advisor_id'], ['id'])
        with op.batch_alter_table('users', naming_convention=NAMING, recreate='always') as b:
            b.create_foreign_key('fk_users_advisor_id_advisor', 'advisor', ['advisor_id'], ['id'])

def _move_data() -> None:
    """Chuyển hồ sơ cố vấn từ lecturer sang advisor, trỏ lại FK, xóa hàng cũ.

    An toàn khi chạy lại: advisor đã tồn tại theo code thì không tạo trùng,
    UPDATE lặp cùng giá trị là vô hại, DELETE có WHERE nên idempotent.
    """
    conn = op.get_bind()

    # Tập hợp id lecturer đang được dùng làm cố vấn: tài khoản role advisor
    # + bất kỳ lớp hành chính nào đã gán advisor_id (kể cả không có tài khoản)
    advisor_lecturer_ids: set[int] = set()
    for (lid,) in conn.execute(
        sa.select(users_t.c.lecturer_id).where(users_t.c.role == 'advisor')
    ):
        if lid is not None:
            advisor_lecturer_ids.add(lid)
    for (lid,) in conn.execute(sa.select(homeroom_t.c.advisor_id)):
        if lid is not None:
            advisor_lecturer_ids.add(lid)

    if not advisor_lecturer_ids:
        return

    # Mỗi lecturer cố vấn → 1 bản ghi advisor (map lecturer.id → advisor.id)
    lect_to_adv: dict[int, int] = {}
    for lect_id in sorted(advisor_lecturer_ids):
        row = conn.execute(
            sa.select(lecturer_t.c.code, lecturer_t.c.name).where(lecturer_t.c.id == lect_id)
        ).first()
        if row is None:
            continue
        code, name = row
        existing = conn.execute(
            sa.select(advisor_t.c.id).where(advisor_t.c.code == code)
        ).first()
        if existing is not None:
            adv_id = existing[0]
        else:
            conn.execute(advisor_t.insert().values(code=code, name=name))
            # Lấy id bằng re-query (sa.table() tối giản — inserted_primary_key
            # không ổn định trên mọi backend)
            (adv_id,) = conn.execute(
                sa.select(advisor_t.c.id).where(advisor_t.c.code == code)
            ).one()
        lect_to_adv[lect_id] = adv_id

    # Trỏ lại users.advisor_id và homeroom_class.advisor_id về bảng advisor
    for uid, lid in conn.execute(
        sa.select(users_t.c.id, users_t.c.lecturer_id).where(users_t.c.role == 'advisor')
    ):
        adv_id = lect_to_adv.get(lid)
        if adv_id is not None:
            conn.execute(
                users_t.update().where(users_t.c.id == uid).values(advisor_id=adv_id)
            )
    for hid, lid in conn.execute(sa.select(homeroom_t.c.id, homeroom_t.c.advisor_id)):
        adv_id = lect_to_adv.get(lid)
        if adv_id is not None:
            conn.execute(
                homeroom_t.update().where(homeroom_t.c.id == hid).values(advisor_id=adv_id)
            )

    # Tài khoản advisor không còn gắn lecturer nữa
    conn.execute(
        users_t.update().where(users_t.c.role == 'advisor').values(lecturer_id=None)
    )

    # Xóa hàng lecturer của cố vấn — chỉ khi không còn tham chiếu nào
    # (không tài khoản lecturer nào khác, không dạy lớp học phần nào)
    for lect_id in sorted(lect_to_adv):
        still_linked = conn.execute(
            sa.select(users_t.c.id).where(users_t.c.lecturer_id == lect_id)
        ).first()
        still_teaching = conn.execute(
            sa.select(course_class_t.c.lecturer_id).where(course_class_t.c.lecturer_id == lect_id)
        ).first()
        if still_linked is None and still_teaching is None:
            conn.execute(lecturer_t.delete().where(lecturer_t.c.id == lect_id))


def upgrade() -> None:
    """Upgrade schema."""
    _create_advisor_table()

    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.add_column('users', sa.Column('advisor_id', sa.Integer(), nullable=True))
        op.create_unique_constraint('users_advisor_id_key', 'users', ['advisor_id'])
    else:
        with op.batch_alter_table('users', naming_convention=NAMING, recreate='always') as b:
            b.add_column(sa.Column('advisor_id', sa.Integer(), nullable=True))
            b.create_unique_constraint('uq_users_advisor_id', ['advisor_id'])

    _drop_old_fks()
    _move_data()
    _add_new_fks()


def downgrade() -> None:
    """Downgrade schema — hoàn tác: trả cố vấn về bảng lecturer."""
    conn = op.get_bind()

    # Tạo lại hàng lecturer từ advisor (đủ cho cả tài khoản advisor lẫn lớp đã gán)
    advisor_ids: set[int] = set()
    for (aid,) in conn.execute(sa.select(users_t.c.advisor_id)):
        if aid is not None:
            advisor_ids.add(aid)
    for (aid,) in conn.execute(sa.select(homeroom_t.c.advisor_id)):
        if aid is not None:
            advisor_ids.add(aid)

    adv_to_lect: dict[int, int] = {}
    for adv_id in sorted(advisor_ids):
        row = conn.execute(
            sa.select(advisor_t.c.code, advisor_t.c.name).where(advisor_t.c.id == adv_id)
        ).first()
        if row is None:
            continue
        code, name = row
        if not code.startswith('DTCCV'):
            # Cố vấn tạo SAU khi tách không xuất thân từ lecturer — không đẩy ngược
            # vào bảng lecturer; FK bị bỏ thì lớp/tài khoản tự chịu dữ liệu rỗng
            continue
        existing = conn.execute(
            sa.select(lecturer_t.c.id).where(lecturer_t.c.code == code)
        ).first()
        if existing is not None:
            lect_id = existing[0]
        else:
            conn.execute(
                lecturer_t.insert().values(code=code, name=name, department=None)
            )
            (lect_id,) = conn.execute(
                sa.select(lecturer_t.c.id).where(lecturer_t.c.code == code)
            ).one()
        adv_to_lect[adv_id] = lect_id

    # Bỏ FK mới trước khi trỏ giá trị ngược về lecturer
    if conn.dialect.name == 'postgresql':
        op.drop_constraint('homeroom_class_advisor_id_fkey', 'homeroom_class', type_='foreignkey')
        op.drop_constraint('users_advisor_id_fkey', 'users', type_='foreignkey')
    else:
        with op.batch_alter_table('homeroom_class', naming_convention=NAMING, recreate='always') as b:
            b.drop_constraint('fk_homeroom_class_advisor_id_advisor', type_='foreignkey')
        with op.batch_alter_table('users', naming_convention=NAMING, recreate='always') as b:
            b.drop_constraint('fk_users_advisor_id_advisor', type_='foreignkey')

    # Trỏ lại users.lecturer_id và homeroom_class.advisor_id về bảng lecturer
    for uid, aid in conn.execute(
        sa.select(users_t.c.id, users_t.c.advisor_id).where(users_t.c.advisor_id.is_not(None))
    ):
        lect_id = adv_to_lect.get(aid)
        if lect_id is not None:
            conn.execute(
                users_t.update().where(users_t.c.id == uid)
                .values(lecturer_id=lect_id, advisor_id=None)
            )
        else:
            conn.execute(users_t.update().where(users_t.c.id == uid).values(advisor_id=None))
    for hid, aid in conn.execute(sa.select(homeroom_t.c.id, homeroom_t.c.advisor_id)):
        lect_id = adv_to_lect.get(aid)
        if lect_id is not None:
            conn.execute(
                homeroom_t.update().where(homeroom_t.c.id == hid).values(advisor_id=lect_id)
            )

    # Khôi phục FK homeroom_class.advisor_id về lecturer (FK users.lecturer_id
    # không bao giờ bị bỏ — giữ nguyên cả hai chiều)
    if conn.dialect.name == 'postgresql':
        op.create_foreign_key(
            'homeroom_class_advisor_id_fkey', 'homeroom_class', 'lecturer',
            ['advisor_id'], ['id'],
        )
    else:
        with op.batch_alter_table('homeroom_class', naming_convention=NAMING, recreate='always') as b:
            b.create_foreign_key('fk_homeroom_class_advisor_id_lecturer', 'lecturer', ['advisor_id'], ['id'])

    # Bỏ cột users.advisor_id rồi bỏ bảng advisor
    if conn.dialect.name == 'postgresql':
        op.drop_constraint('users_advisor_id_key', 'users', type_='unique')
        op.drop_column('users', 'advisor_id')
    else:
        with op.batch_alter_table('users', naming_convention=NAMING, recreate='always') as b:
            b.drop_column('advisor_id')
    op.drop_index('ix_advisor_name', table_name='advisor')
    op.drop_table('advisor')
