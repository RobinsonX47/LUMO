document.addEventListener('DOMContentLoaded', function () {
	// Generic file input handler: any <input class="file-input"> will update
	// a sibling .file-name element and optionally update a preview image.
	const fileInputs = document.querySelectorAll('input[type="file"]');
	fileInputs.forEach(function (input) {
		input.addEventListener('change', function () {
			const id = this.id;
			const file = this.files && this.files[0];
			const filenameEl = document.getElementById(id + (id === 'poster_h' ? 'Filename' : 'Filename')) || document.getElementById(id + 'Filename');
			// fallback: find nearby .file-name
			let fileNameNode = filenameEl;
			if (!fileNameNode) {
				fileNameNode = this.parentElement.querySelector('.file-name');
			}

			if (!file) {
				if (fileNameNode) fileNameNode.textContent = 'No file chosen';
				return;
			}

			if (fileNameNode) fileNameNode.textContent = file.name;

			// If there's a target preview element (data-preview="id"), update it
			const previewTarget = this.dataset.preview ? document.getElementById(this.dataset.preview) : null;
			if (file.type && file.type.startsWith('image/') && previewTarget) {
				const reader = new FileReader();
				reader.onload = function (e) {
					if (previewTarget.tagName === 'IMG') previewTarget.src = e.target.result;
					else previewTarget.style.backgroundImage = 'url(' + e.target.result + ')';
					// if preview sits inside .avatar-wrap, add has-avatar
					const wrap = previewTarget.closest('.avatar-wrap');
					if (wrap) wrap.classList.add('has-avatar');
				};
				reader.readAsDataURL(file);
			}
		});
	});
});
