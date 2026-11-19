FROM frappe/erpnext:develop

USER frappe

# Install healthcare without building frontend assets during docker build
RUN cd /home/frappe/frappe-bench \
    && bench get-app --branch develop --skip-assets https://github.com/frappe/health

# Copy and install local opd_clinic_1 app
COPY --chown=frappe:frappe . /home/frappe/frappe-bench/apps/opd_clinic_1
RUN /home/frappe/frappe-bench/env/bin/pip install -e /home/frappe/frappe-bench/apps/opd_clinic_1
